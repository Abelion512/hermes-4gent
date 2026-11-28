import { type NoProviderFixture, setupNoProvider } from './fixtures'
import { rendererCss } from './renderer-css'
import { expect, test } from './test'

let fixture: NoProviderFixture | null = null

test.beforeAll(async () => {
  fixture = await setupNoProvider()
})

test.afterAll(async () => {
  await fixture?.cleanup()
  fixture = null
})

// useStickyPromptClip writes this value on every scroll frame onto whole turns.
// If it inherits, each write restyles the turn's entire subtree (#99889).
test('the sticky-prompt clip applies to its host without inheriting into the turn', async () => {
  const page = fixture!.page

  await page.setContent(`
    <style>${rendererCss()}</style>
    <div data-sticky-prompt-clip data-testid="host" style="--sticky-prompt-clip: 24px">
      <p data-testid="child">covered turn content</p>
    </div>
  `)

  const styles = await page.getByTestId('host').evaluate(host => ({
    childClip: getComputedStyle(host.querySelector('p')!).getPropertyValue('--sticky-prompt-clip').trim(),
    hostClipPath: getComputedStyle(host).clipPath
  }))

  expect(styles.hostClipPath).toBe('inset(24px 0px 0px)')
  expect(styles.childClip).toBe('0px')
})
