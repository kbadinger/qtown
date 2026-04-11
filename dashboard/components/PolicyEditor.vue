<script setup lang="ts">
// PolicyEditor — a syntax-highlighted code editor component.
//
// Props:
//   modelValue   — current source code (v-model)
//   language     — syntax highlight language ('rust' | 'json' | 'text')
//   readOnly     — disables editing (defaults to false)
//
// Features:
//   - Monospace font, line numbers, dark theme matching qtown-bg
//   - Tab key inserts 4 spaces instead of moving focus
//   - Basic syntax highlighting for Rust keywords overlaid on a <textarea>
//   - Min height 400px, vertically resizable
//   - Scroll is synchronised between the highlight layer and the textarea

const props = withDefaults(defineProps<{
  modelValue: string
  language?: string
  readOnly?: boolean
}>(), {
  language: 'rust',
  readOnly: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

// ─── Refs ──────────────────────────────────────────────────────────────────

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const highlightRef = ref<HTMLPreElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)

// ─── Computed: highlighted HTML ───────────────────────────────────────────

const highlightedHtml = computed(() => {
  const code = props.modelValue
  if (props.language !== 'rust') {
    return escapeHtml(code)
  }
  return highlightRust(code)
})

// ─── Computed: line numbers ───────────────────────────────────────────────

const lineNumbers = computed(() => {
  const lines = props.modelValue.split('\n')
  return lines.map((_, i) => i + 1)
})

// ─── Scroll sync ─────────────────────────────────────────────────────────

function syncScroll() {
  if (!textareaRef.value || !highlightRef.value) return
  highlightRef.value.scrollTop = textareaRef.value.scrollTop
  highlightRef.value.scrollLeft = textareaRef.value.scrollLeft
}

// ─── Key handler ─────────────────────────────────────────────────────────

function handleKeydown(event: KeyboardEvent) {
  if (props.readOnly) return

  const ta = event.target as HTMLTextAreaElement

  if (event.key === 'Tab') {
    event.preventDefault()
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const spaces = '    ' // 4 spaces

    const newValue =
      props.modelValue.slice(0, start) + spaces + props.modelValue.slice(end)
    emit('update:modelValue', newValue)

    // Restore cursor after Vue updates the DOM.
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.selectionStart = start + 4
        textareaRef.value.selectionEnd = start + 4
      }
    })
  }
}

// ─── Input handler ────────────────────────────────────────────────────────

function handleInput(event: Event) {
  const ta = event.target as HTMLTextAreaElement
  emit('update:modelValue', ta.value)
}

// ─── Syntax highlight: Rust ───────────────────────────────────────────────

const RUST_KEYWORDS = [
  'fn', 'let', 'if', 'else', 'return', 'pub', 'extern', 'struct', 'impl',
  'use', 'mod', 'match', 'for', 'while', 'loop', 'break', 'continue', 'in',
  'const', 'static', 'mut', 'ref', 'type', 'trait', 'where', 'enum', 'self',
  'Self', 'super', 'crate', 'move', 'async', 'await', 'true', 'false',
  'Some', 'None', 'Ok', 'Err', 'Vec', 'String', 'Option', 'Result',
]

const RUST_TYPES = [
  'i8', 'i16', 'i32', 'i64', 'i128', 'isize',
  'u8', 'u16', 'u32', 'u64', 'u128', 'usize',
  'f32', 'f64', 'bool', 'char', 'str',
]

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function highlightRust(code: string): string {
  const lines = code.split('\n')
  return lines
    .map((line) => highlightLine(line))
    .join('\n')
}

function highlightLine(line: string): string {
  // Handle full-line and end-of-line comments.
  const commentIdx = line.indexOf('//')
  if (commentIdx !== -1) {
    const before = line.slice(0, commentIdx)
    const comment = line.slice(commentIdx)
    return highlightTokens(before) +
      `<span class="hl-comment">${escapeHtml(comment)}</span>`
  }
  return highlightTokens(line)
}

function highlightTokens(text: string): string {
  // Tokenise the line preserving whitespace and special chars.
  // Strategy: split on word boundaries, then classify each token.
  const parts: string[] = []
  let i = 0

  while (i < text.length) {
    // String literal
    if (text[i] === '"') {
      let j = i + 1
      while (j < text.length && text[j] !== '"') {
        if (text[j] === '\\') j++ // skip escape
        j++
      }
      j++ // closing quote
      parts.push(`<span class="hl-string">${escapeHtml(text.slice(i, j))}</span>`)
      i = j
      continue
    }

    // Char literal
    if (text[i] === "'") {
      let j = i + 1
      if (text[j] === '\\') j++
      j += 2 // char + closing quote
      parts.push(`<span class="hl-string">${escapeHtml(text.slice(i, j))}</span>`)
      i = j
      continue
    }

    // Word (keyword / type / identifier)
    if (/[a-zA-Z_]/.test(text[i])) {
      let j = i + 1
      while (j < text.length && /[a-zA-Z0-9_]/.test(text[j])) j++
      const word = text.slice(i, j)
      if (RUST_KEYWORDS.includes(word)) {
        parts.push(`<span class="hl-keyword">${word}</span>`)
      } else if (RUST_TYPES.includes(word)) {
        parts.push(`<span class="hl-type">${word}</span>`)
      } else if (/^[A-Z]/.test(word)) {
        parts.push(`<span class="hl-type">${escapeHtml(word)}</span>`)
      } else {
        parts.push(escapeHtml(word))
      }
      i = j
      continue
    }

    // Number
    if (/[0-9]/.test(text[i])) {
      let j = i + 1
      while (j < text.length && /[0-9._xbXBoO]/.test(text[j])) j++
      parts.push(`<span class="hl-number">${escapeHtml(text.slice(i, j))}</span>`)
      i = j
      continue
    }

    // Macro invocation (word!)
    // Handled already by word rule above; the `!` is a separate character.

    // Attribute / annotation
    if (text[i] === '#' && text[i + 1] === '[') {
      let j = i + 1
      while (j < text.length && text[j] !== ']') j++
      j++ // closing bracket
      parts.push(`<span class="hl-attr">${escapeHtml(text.slice(i, j))}</span>`)
      i = j
      continue
    }

    // Lifetime
    if (text[i] === "'" && i + 1 < text.length && /[a-z]/.test(text[i + 1])) {
      let j = i + 1
      while (j < text.length && /[a-z_]/.test(text[j])) j++
      parts.push(`<span class="hl-lifetime">${escapeHtml(text.slice(i, j))}</span>`)
      i = j
      continue
    }

    // Everything else (operators, punctuation, whitespace)
    parts.push(escapeHtml(text[i]))
    i++
  }

  return parts.join('')
}
</script>

<template>
  <div
    ref="containerRef"
    class="policy-editor"
    :class="{ 'policy-editor--readonly': readOnly }"
  >
    <!-- Line numbers gutter -->
    <div class="policy-editor__gutter" aria-hidden="true">
      <div
        v-for="n in lineNumbers"
        :key="n"
        class="policy-editor__line-num"
      >
        {{ n }}
      </div>
    </div>

    <!-- Highlight layer (display only, pointer-events: none) -->
    <pre
      ref="highlightRef"
      class="policy-editor__highlight"
      aria-hidden="true"
      v-html="highlightedHtml + '\n'"
    />

    <!-- Editable textarea -->
    <textarea
      ref="textareaRef"
      class="policy-editor__textarea"
      :value="modelValue"
      :readonly="readOnly"
      :aria-label="readOnly ? 'Policy source (read-only)' : 'Policy source editor'"
      spellcheck="false"
      autocorrect="off"
      autocapitalize="off"
      autocomplete="off"
      @input="handleInput"
      @keydown="handleKeydown"
      @scroll="syncScroll"
    />
  </div>
</template>

<style scoped>
.policy-editor {
  position: relative;
  display: flex;
  min-height: 400px;
  resize: vertical;
  overflow: hidden;
  background: #0d0d1a;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #c8d3f5;
}

.policy-editor--readonly {
  opacity: 0.85;
}

/* Line numbers gutter */
.policy-editor__gutter {
  flex-shrink: 0;
  width: 44px;
  padding: 12px 8px 12px 4px;
  background: #0a0a15;
  border-right: 1px solid #1e1e36;
  text-align: right;
  user-select: none;
  overflow: hidden;
  color: #3d3d6b;
}

.policy-editor__line-num {
  height: calc(1em * 1.6);
  font-size: 11px;
  line-height: 1.6;
}

/* Highlight overlay */
.policy-editor__highlight {
  position: absolute;
  top: 0;
  left: 44px;
  right: 0;
  bottom: 0;
  padding: 12px 14px;
  margin: 0;
  overflow: hidden;
  white-space: pre;
  word-wrap: normal;
  pointer-events: none;
  font: inherit;
  color: transparent; /* text itself is hidden; spans provide color */
}

/* Editable textarea sits on top */
.policy-editor__textarea {
  position: absolute;
  top: 0;
  left: 44px;
  right: 0;
  bottom: 0;
  padding: 12px 14px;
  margin: 0;
  width: calc(100% - 44px);
  height: 100%;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: transparent;
  caret-color: #c8d3f5;
  font: inherit;
  white-space: pre;
  overflow: auto;
  tab-size: 4;
  -moz-tab-size: 4;
}

.policy-editor__textarea::selection {
  background: rgba(130, 170, 255, 0.2);
  color: transparent;
}

/* ─── Syntax highlight token colours ─────────────────────────────────────── */

:deep(.hl-keyword)  { color: #c792ea; font-weight: 600; }
:deep(.hl-type)     { color: #82aaff; }
:deep(.hl-string)   { color: #c3e88d; }
:deep(.hl-number)   { color: #f78c6c; }
:deep(.hl-comment)  { color: #546e7a; font-style: italic; }
:deep(.hl-attr)     { color: #ffcb6b; }
:deep(.hl-lifetime) { color: #ff5370; }
</style>
