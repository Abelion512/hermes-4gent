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
