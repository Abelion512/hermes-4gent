import { describe, expect, it } from 'vitest'

import { BUILTIN_THEME_LIST, DEFAULT_TYPOGRAPHY, nousTheme } from './presets'

// #40364: none of the UI text/mono fonts carry emoji glyphs, so every font
// stack must end with a color-emoji fallback or emoji render as tofu on
// platforms whose default font lacks them (e.g. Linux).
describe('theme typography emoji fallback (#40364)', () => {
  const stacks: Array<[string, string]> = [
    ['DEFAULT_TYPOGRAPHY.fontSans', DEFAULT_TYPOGRAPHY.fontSans],
    ['DEFAULT_TYPOGRAPHY.fontMono', DEFAULT_TYPOGRAPHY.fontMono],
    // A theme may override only fontMono (fontSans then falls back to the
    // default, which already carries the emoji stack), so skip undefined.
    ...BUILTIN_THEME_LIST.flatMap(theme =>
      (
        [
          [`${theme.name}.fontSans`, theme.typography?.fontSans],
          [`${theme.name}.fontMono`, theme.typography?.fontMono]
        ] as Array<[string, string | undefined]>
      ).filter((entry): entry is [string, string] => typeof entry[1] === 'string')
    )
  ]

  it.each(stacks)('%s includes a color-emoji font', (_label, stack) => {
    expect(stack).toMatch(/Apple Color Emoji|Segoe UI Emoji|Noto Color Emoji|(^|,\s*)emoji\b/)
  })
})

describe('theme typography Latin Extended fallback (#61392)', () => {
  const monoStacks: Array<[string, string]> = [
    ['DEFAULT_TYPOGRAPHY.fontMono', DEFAULT_TYPOGRAPHY.fontMono],
    ...BUILTIN_THEME_LIST.map(
      theme =>
        [
          `${theme.name}.effectiveFontMono`,
          theme.typography?.fontMono ?? nousTheme.typography?.fontMono ?? DEFAULT_TYPOGRAPHY.fontMono
        ] as [string, string]
    )
  ]

  it.each(monoStacks)('%s falls back to bundled JetBrains Mono before generic fonts', (_label, stack) => {
    const jetbrains = stack.indexOf('JetBrains Mono')

    expect(jetbrains).toBeGreaterThanOrEqual(0)

    const genericIndexes = [
      stack.indexOf('ui-monospace'),
      stack.indexOf('monospace'),
      stack.indexOf('Apple Color Emoji'),
      stack.indexOf('Segoe UI Emoji'),
      stack.indexOf('Noto Color Emoji')
    ].filter(index => index >= 0)

    expect(genericIndexes.length).toBeGreaterThan(0)
    expect(jetbrains).toBeLessThan(Math.min(...genericIndexes))
  })

  it('default stack includes common Linux monospace glyph fallbacks', () => {
    expect(DEFAULT_TYPOGRAPHY.fontMono).toContain('DejaVu Sans Mono')
    expect(DEFAULT_TYPOGRAPHY.fontMono).toContain('Liberation Mono')
    expect(DEFAULT_TYPOGRAPHY.fontMono).toContain('Noto Sans Mono')
  })
})

describe('Paper themes', () => {
  const gray = BUILTIN_THEME_LIST.find(t => t.name === 'paper')
  const warm = BUILTIN_THEME_LIST.find(t => t.name === 'paper-warm')

  it('registers both selectable variants under distinct keys; paper key keeps working', () => {
    expect(gray?.label).toBe('Paper Gray')
    expect(warm?.label).toBe('Paper Warm')
    expect(new Set(BUILTIN_THEME_LIST.map(t => t.name)).size).toBe(BUILTIN_THEME_LIST.length)
  })

  it('light palettes differ, dark palette is shared', () => {
    expect(gray?.colors.background).toBe('#B4B0A6')
    expect(warm?.colors.background).toBe('#C2BBAD')
    expect(warm?.colors.sidebarBackground).toBe('#B8B1A3')
    expect(gray?.colors.sidebarBackground).toBe('#B8B1A3')
    expect(warm?.darkColors).toEqual(gray?.darkColors)
  })

  it('has no near-white light surfaces', () => {
    for (const t of [gray, warm]) {
      for (const k of ['background', 'card', 'popover', 'secondary', 'sidebarBackground', 'muted'] as const) {
        const value = t!.colors[k]
        expect(value, `${t!.name}.${k} defined`).toBeTruthy()
        const hex = (value ?? '').replace('#', '')
        const lum = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).reduce((a, b) => a + b, 0) / 3
        expect(lum, `${t!.name}.${k}`).toBeLessThan(0.8)
      }
    }
  })

  it('swaps accent and surfaces in custom CSS without leaking the other palette', () => {
    expect(warm?.customCSS).toContain('#CCC5B8')
    expect(warm?.customCSS).not.toContain('#BDB9AF')
    expect(gray?.customCSS).toContain('#BDB9AF')
    expect(gray?.customCSS).not.toContain('#CCC5B8')
    expect(gray?.customCSS).toContain('html.dark{--ui-stroke-primary:#7A7A7A')
    expect(warm?.customCSS).toContain('html.dark{--ui-stroke-primary:#7A7A7A')
    expect(gray?.customCSS).toContain('#768390')
    expect(warm?.customCSS).toContain('#768390')
  })
})
