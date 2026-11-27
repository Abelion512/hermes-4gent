import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { parseListings } from '@/lib/listing-embed'

import { ProductRow } from './product-row'

const A = 'https://img.example/a.jpg'
const B = 'https://img.example/b.jpg'

const listings = parseListings(
  JSON.stringify([
    {
      catches: ['Soldered RAM'],
      facts: ['16 GB RAM', 'OLED'],
      images: [A, B],
      kind: 'product',
      links: ['https://shop.example/a'],
      note: 'Light and quiet.',
      price: 'Rp 15.000.000',
      pros: ['Long battery', 'Bright screen'],
      title: 'Laptop A'
    },
    { kind: 'product', note: 'Second note.', pros: ['Cheap'], title: 'Laptop B' },
    { kind: 'product', title: 'Laptop C', images: ['https://img.example/c.jpg'] }
  ])
)

afterEach(cleanup)

const cards = (root: HTMLElement) => Array.from(root.querySelectorAll<HTMLElement>('[data-slot="aui_product-card"]'))

describe('ProductRow', () => {
  it('renders one compact card per product, with no detail until opened', () => {
    const { container } = render(<ProductRow listings={listings} />)

    expect(cards(container)).toHaveLength(3)
    expect(screen.getByText('Laptop A')).toBeTruthy()
    expect(screen.getByText('Rp 15.000.000')).toBeTruthy()
    expect(screen.getByText('16 GB RAM · OLED')).toBeTruthy()
    expect(screen.queryByText('Long battery')).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('shows only the first photo on the card', () => {
    const { container } = render(<ProductRow listings={listings} />)
    const imgs = cards(container)[0].querySelectorAll('img')

    expect(imgs).toHaveLength(1)
    expect(imgs[0].getAttribute('src')).toBe(A)
    expect(imgs[0].getAttribute('referrerpolicy')).toBe('no-referrer')
  })

  it('opens the detail popup from the card body with note, pros, catches and a safe source link', () => {
    render(<ProductRow listings={listings} />)
    fireEvent.click(screen.getByText('Laptop A'))

    const dialog = screen.getByRole('dialog')

    expect(within(dialog).getByText('Light and quiet.')).toBeTruthy()
    expect(within(dialog).getByText('Long battery')).toBeTruthy()
    expect(within(dialog).getByText('Bright screen')).toBeTruthy()
    expect(within(dialog).getByText('Soldered RAM')).toBeTruthy()

    const link = within(dialog).getByText('shop.example').closest('a')!

    expect(link.getAttribute('href')).toBe('https://shop.example/a')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('each card opens its own detail, not the first one', () => {
    render(<ProductRow listings={listings} />)
    fireEvent.click(screen.getByText('Laptop B'))

    const dialog = screen.getByRole('dialog')

    expect(within(dialog).getByText('Second note.')).toBeTruthy()
    expect(within(dialog).queryByText('Light and quiet.')).toBeNull()
  })

  it('opens the image viewer, not the popup, from the photo', () => {
    render(<ProductRow listings={listings} />)
    fireEvent.click(screen.getAllByRole('button', { name: /Laptop A/ })[0])

    expect(screen.queryByText('Long battery')).toBeNull()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('labels photo buttons distinctly and keeps images decorative for screen readers', () => {
    const { container } = render(<ProductRow listings={listings} />)

    expect(screen.getByRole('button', { name: 'Open image: Laptop A' })).toBeTruthy()
    expect(cards(container)[0].querySelector('img')!.getAttribute('alt')).toBe('')

    fireEvent.click(screen.getByText('Laptop A'))

    expect(screen.getByRole('button', { name: 'Open image 1/2' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /2\/2$/ })).toBeTruthy()
  })

  it('drops a broken photo and falls through to the next one', () => {
    const { container } = render(<ProductRow listings={listings} />)
    const img = () => cards(container)[0].querySelector('img')!

    expect(img().getAttribute('src')).toBe(A)
    fireEvent.error(img())
    expect(img().getAttribute('src')).toBe(B)
    fireEvent.error(img())
    // Every photo dead: no tile left, the text still renders.
    expect(cards(container)[0].querySelector('img')).toBeNull()
    expect(screen.getByText('Laptop A')).toBeTruthy()
  })

  it('renders no photo button for a card without images', () => {
    const { container } = render(<ProductRow listings={listings} />)

    expect(cards(container)[1].querySelector('img')).toBeNull()
    expect(within(cards(container)[1]).queryByRole('button', { name: /Open image/ })).toBeNull()
    fireEvent.click(screen.getByText('Laptop B'))
    const dg = screen.getByRole('dialog')
    const hd = within(dg).getAllByText('Laptop B')[0].parentElement?.className
    expect(hd).toContain('pr-8')
  })

  it('renders model text as text, not markup', () => {
    const nasty = parseListings('[{"kind":"product","title":"<img src=x onerror=alert(1)>","note":"<b>hi</b>"}]')
    const { container } = render(<ProductRow listings={nasty} />)

    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy()
  })
})
