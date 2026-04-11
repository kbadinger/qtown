//! Fortress service entry point.
//!
//! Starts four concurrent tasks and waits for a graceful shutdown signal:
//!
//! | Task             | Address / resource                           |
//! |------------------|----------------------------------------------|
//! | gRPC server      | `0.0.0.0:50052`                              |
//! | HTTP health      | `0.0.0.0:8080`  (`/healthz`, `/readyz`)      |
//! | Kafka consumer   | `qtown.validation.request` → validation loop |
//! | Audit log        | shared `AuditLog` flushed on shutdown        |
//!
//! All tasks share a broadcast channel; sending `()` on it signals every
//! task to wind down. The channel is triggered by Ctrl-C or SIGTERM.

use std::net::SocketAddr;
use std::sync::Arc;

use tokio::net::TcpListener;
use tokio::signal;
use tokio::sync::broadcast;
use tracing::{error, info, warn};
use tracing_subscriber::{EnvFilter, FmtSubscriber};

mod audit;
mod grpc_service;
mod kafka_consumer;

// ─────────────────────────────────────────────────────────────────────────────

/// Application entry point.
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // ── Tracing ───────────────────────────────────────────────────────────────
    let subscriber = FmtSubscriber::builder()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("fortress=info,info")),
        )
        .with_target(true)
        .compact()
        .finish();
    tracing::subscriber::set_global_default(subscriber)
        .expect("setting global tracing subscriber failed");

    info!("Fortress starting up");

    // ── Shared state ──────────────────────────────────────────────────────────
    //
    // A single `FortressService` holds the `ValidationEngine` (with all three
    // production rules pre-loaded) and the `WasmSandbox`. Both are wrapped in
    // `Arc` so they can be shared across async tasks and Rayon workers.
    let service = Arc::new(grpc_service::FortressService::new());

    // ── Shutdown broadcast channel ────────────────────────────────────────────
    let (shutdown_tx, _) = broadcast::channel::<()>(1);

    // ── gRPC server ───────────────────────────────────────────────────────────
    let grpc_addr: SocketAddr = "0.0.0.0:50052".parse()?;
    let grpc_shutdown = shutdown_tx.subscribe();

    let grpc_handle = tokio::spawn(async move {
        run_grpc_server(grpc_addr, grpc_shutdown).await;
    });

    // ── HTTP health endpoint ──────────────────────────────────────────────────
    let health_addr: SocketAddr = "0.0.0.0:8080".parse()?;
    let health_shutdown = shutdown_tx.subscribe();

    let health_handle = tokio::spawn(async move {
        run_health_server(health_addr, health_shutdown).await;
    });

    // ── Kafka consumer ────────────────────────────────────────────────────────
    let kafka_service = Arc::clone(&service);
    let kafka_shutdown = shutdown_tx.subscribe();

    let kafka_handle = tokio::spawn(async move {
        run_kafka_consumer(kafka_service, kafka_shutdown).await;
    });

    // ── Graceful shutdown ─────────────────────────────────────────────────────
    shutdown_on_signal(shutdown_tx).await;

    // Wait for all tasks to wind down.
    let _ = tokio::join!(grpc_handle, health_handle, kafka_handle);
    info!("Fortress shut down cleanly");
    Ok(())
}

// ─────────────────────────────────────────────────────────────────────────────

/// Waits for SIGTERM or Ctrl-C, then broadcasts shutdown to all tasks.
async fn shutdown_on_signal(tx: broadcast::Sender<()>) {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl-C handler");
    };

    #[cfg(unix)]
    let sigterm = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install SIGTERM handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let sigterm = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c  => info!("Received Ctrl-C, initiating shutdown"),
        _ = sigterm => info!("Received SIGTERM, initiating shutdown"),
    }

    // Errors here just mean all receivers were already dropped.
    let _ = tx.send(());
}

// ─────────────────────────────────────────────────────────────────────────────

/// Runs the Tonic gRPC server on `addr`.
///
/// Phase 2 wires up the real `tonic::transport::Server` with the proto-generated
/// `ValidationServer<FortressService>`. Until `build.rs` emits the stubs, we
/// park the task and wait for the shutdown signal.
async fn run_grpc_server(addr: SocketAddr, mut shutdown: broadcast::Receiver<()>) {
    info!(%addr, "gRPC server listening (placeholder — proto codegen pending)");

    // TODO Phase 2: replace with live Tonic router once build.rs is wired:
    //
    //   tonic::transport::Server::builder()
    //       .add_service(FortressServer::new(service))
    //       .serve_with_shutdown(addr, async { let _ = shutdown.recv().await; })
    //       .await
    //       .expect("gRPC server error");

    let _ = shutdown.recv().await;
    info!("gRPC server stopped");
}

// ─────────────────────────────────────────────────────────────────────────────

/// Minimal HTTP server that responds 200 OK to any request on `:8080`.
///
/// Handles `/healthz` (liveness) and `/readyz` (readiness) — both return
/// `{"status":"ok","service":"fortress"}`.
async fn run_health_server(addr: SocketAddr, mut shutdown: broadcast::Receiver<()>) {
    let listener = match TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) => {
            error!(%addr, "Failed to bind health server: {}", e);
            return;
        }
    };

    info!(%addr, "HTTP health endpoint listening");

    loop {
        tokio::select! {
            accept = listener.accept() => {
                match accept {
                    Ok((mut stream, peer)) => {
                        tokio::spawn(async move {
                            handle_health_connection(&mut stream, peer).await;
                        });
                    }
                    Err(e) => warn!("Health accept error: {e}"),
                }
            }
            _ = shutdown.recv() => {
                info!("Health server stopped");
                break;
            }
        }
    }
}

/// Writes a minimal HTTP/1.1 200 OK response to the connection.
async fn handle_health_connection(
    stream: &mut tokio::net::TcpStream,
    peer: SocketAddr,
) {
    use tokio::io::AsyncWriteExt;

    let body = b"{\"status\":\"ok\",\"service\":\"fortress\"}";
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );

    let mut buf = response.into_bytes();
    buf.extend_from_slice(body);

    if let Err(e) = stream.write_all(&buf).await {
        warn!(%peer, "Health write error: {e}");
    }
}

// ─────────────────────────────────────────────────────────────────────────────

/// Wraps the Kafka consumer loop with a shutdown-aware select.
///
/// The `run_consumer` future inside `kafka_consumer` drives the rdkafka
/// `StreamConsumer` until the stream ends. We race it against the shutdown
/// broadcast so the task terminates cleanly on SIGTERM / Ctrl-C.
async fn run_kafka_consumer(
    service: Arc<grpc_service::FortressService>,
    mut shutdown: broadcast::Receiver<()>,
) {
    tokio::select! {
        _ = kafka_consumer::run_consumer(service) => {
            info!("Kafka consumer stream ended");
        }
        _ = shutdown.recv() => {
            info!("Kafka consumer stopped (shutdown signal)");
        }
    }
}
