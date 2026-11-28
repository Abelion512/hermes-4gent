import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { afterAll, expect, test } from 'vitest'

import { entryStylesheets, rendererCss } from './renderer-css'

const made: string[] = []

function dist(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'renderer-css-'))

  made.push(dir)
  fs.mkdirSync(path.join(dir, 'assets'))

  return dir
}

const write = (dir: string, rel: string, text: string): void => fs.writeFileSync(path.join(dir, rel), text)

afterAll(() => {
  for (const dir of made) {
    fs.rmSync(dir, { force: true, recursive: true })
  }
})

test('reads the stylesheet index.html links, whatever the bundler named it', () => {
  const dir = dist()

  write(dir, 'assets/main-AB.css', '.main{}')
  write(dir, 'assets/tooltip-X.css', '.tip{}')
  write(dir, 'index.html', '<html><head><link rel="stylesheet" crossorigin href="./assets/main-AB.css"></head></html>')
  expect(rendererCss(dir)).toBe('.main{}')
})

test('still reads an index-<hash>.css layout, with an absolute href and a query', () => {
  const dir = dist()

  write(dir, 'assets/index-1.css', '.old{}')
  write(dir, 'index.html', '<link href="/assets/index-1.css?v=2" rel="stylesheet">')
  expect(rendererCss(dir)).toBe('.old{}')
})

test('falls back to the entry css in renderer-manifest.json and ignores non-entry chunks', () => {
  const dir = dist()

  write(dir, 'assets/main-M.css', '.m{}')
  write(dir, 'renderer-manifest.json', JSON.stringify({ 'index.html': { css: ['assets/main-M.css'], isEntry: true }, 'x.js': { css: ['assets/z.css'] } }))
  expect(rendererCss(dir)).toBe('.m{}')
})

test('reads a stylesheet named by both sources once', () => {
  const dir = dist()

  write(dir, 'assets/main-AB.css', '.a{}')
  write(dir, 'index.html', '<link rel="stylesheet" href="./assets/main-AB.css">')
  write(dir, 'renderer-manifest.json', JSON.stringify({ e: { css: ['assets/main-AB.css'], isEntry: true } }))
  expect(entryStylesheets(dir)).toHaveLength(1)
})

test('fails loudly and names the css files present when no entry stylesheet resolves', () => {
  const dir = dist()

  write(dir, 'assets/tooltip-X.css', '.tip{}')
  expect(() => rendererCss(dir)).toThrow(/entry stylesheet not found.*tooltip-X\.css/)
})

test('a link to a file that does not exist does not count', () => {
  const dir = dist()

  write(dir, 'index.html', '<link rel="stylesheet" href="./assets/gone.css">')
  expect(() => rendererCss(dir)).toThrow(/not found/)
})

test('follows the single dynamic boot edge when the app sits behind import("./main")', () => {
  const dir = dist()

  // Production layout: src/entry.ts dynamically imports ./main, so index.html has no
  // stylesheet link and the isEntry chunk carries no css; the boot styles live on the
  // entry's isDynamicEntry chunk (emitted as main-<hash>.css).
  write(dir, 'index.html', '<html><head><script type="module" src="./assets/index-E.js"></script></head></html>')
  write(dir, 'assets/main-M.css', '.boot{}')
  write(
    dir,
    'renderer-manifest.json',
    JSON.stringify({
      'index.html': { file: 'assets/index-E.js', isEntry: true, dynamicImports: ['src/main.tsx'] },
      'src/main.tsx': { file: 'assets/main-M.js', isDynamicEntry: true, css: ['assets/main-M.css'] }
    })
  )
  expect(rendererCss(dir)).toBe('.boot{}')
})

test('the boot walk stops at one dynamic edge and skips lazy routes and secondary windows', () => {
  const dir = dist()

  write(dir, 'index.html', '<script type="module" src="./assets/index-E.js"></script>')
  write(dir, 'assets/main-M.css', '.boot{}')
  write(dir, 'assets/vendor-V.css', '.vendor{}')
  write(dir, 'assets/tour-T.css', '.tour{}')
  write(dir, 'assets/wake-W.css', '.wake{}')
  write(
    dir,
    'renderer-manifest.json',
    JSON.stringify({
      'index.html': { file: 'assets/index-E.js', isEntry: true, imports: ['_vendor.js'], dynamicImports: ['src/main.tsx'] },
      '_vendor.js': { file: 'assets/vendor-V.js', css: ['assets/vendor-V.css'] },
      'src/main.tsx': {
        file: 'assets/main-M.js',
        isDynamicEntry: true,
        css: ['assets/main-M.css'],
        dynamicImports: ['src/tour.ts', 'src/wake-root.ts']
      },
      'src/tour.ts': { file: 'assets/tour-T.js', isDynamicEntry: true, css: ['assets/tour-T.css'] },
      'src/wake-root.ts': { file: 'assets/wake-W.js', isDynamicEntry: true, css: ['assets/wake-W.css'] }
    })
  )
  const css = rendererCss(dir)
  expect(css).toContain('.vendor{}')
  expect(css).toContain('.boot{}')
  expect(css).not.toContain('.tour{}')
  expect(css).not.toContain('.wake{}')
})

test('a dynamic chunk named by the boot edge that does not exist on disk does not count', () => {
  const dir = dist()

  write(dir, 'index.html', '<script type="module" src="./assets/index-E.js"></script>')
  write(
    dir,
    'renderer-manifest.json',
    JSON.stringify({
      'index.html': { file: 'assets/index-E.js', isEntry: true, dynamicImports: ['src/main.tsx'] },
      'src/main.tsx': { file: 'assets/main-M.js', isDynamicEntry: true, css: ['assets/gone.css'] }
    })
  )
  expect(() => rendererCss(dir)).toThrow(/not found/)
})
