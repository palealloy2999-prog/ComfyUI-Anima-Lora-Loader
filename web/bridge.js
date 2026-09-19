// LoRA Manager owns the list rendering and synchronization rules.
export function connectWidgets(node, synchronization) {
  const text = node.widgets?.find((widget) => widget.name === 'text')
  const loras = node.widgets?.find((widget) => widget.name === 'loras')
  if (!text || !loras || node.__animaConnected || !synchronization) return
  const { mergeLoras, applyLoraValuesToText } = synchronization
  if (typeof mergeLoras !== 'function' || typeof applyLoraValuesToText !== 'function') return
  node.__animaConnected = true
  node.serialize_widgets = true
  let isUpdating = false
  const textCallback = text.callback
  const listCallback = loras.callback
  text.callback = function (value, ...args) {
    if (isUpdating) return
    isUpdating = true
    try {
      textCallback?.call(this, value, ...args)
      loras.value = mergeLoras(value, loras.value ?? [])
    } finally {
      isUpdating = false
    }
  }
  loras.callback = function (value, ...args) {
    if (isUpdating) return
    isUpdating = true
    try {
      listCallback?.call(this, value, ...args)
      text.value = applyLoraValuesToText(text.value, value ?? loras.value ?? [])
    } finally {
      isUpdating = false
    }
  }
}

export function preserveZeroClip(widget) {
  // The installed Manager's setter uses `clipStrength || strength`.
  // Its numeric controls accept "0"; serialize back to an actual number.
  if (Object.prototype.hasOwnProperty.call(widget, '__animaZeroClipPreserved')) return
  let owner = widget
  let descriptor
  while (owner && !(descriptor = Object.getOwnPropertyDescriptor(owner, 'value'))) {
    owner = Object.getPrototypeOf(owner)
  }
  if (!descriptor?.get || !descriptor?.set || (owner === widget && !descriptor.configurable)) return
  Object.defineProperty(widget, 'value', {
    configurable: true,
    get() {
      const value = descriptor.get.call(this)
      return Array.isArray(value)
        ? value.map((entry) => ({
            ...entry,
            clipStrength: Number(entry.clipStrength ?? entry.strength),
          }))
        : value
    },
    set(value) {
      descriptor.set.call(
        this,
        Array.isArray(value)
          ? value.map((entry) => ({
              ...entry,
              clipStrength: Number(entry.clipStrength) === 0 ? '0' : entry.clipStrength,
            }))
          : value
      )
    },
  })
  Object.defineProperty(widget, '__animaZeroClipPreserved', { value: true })
}
