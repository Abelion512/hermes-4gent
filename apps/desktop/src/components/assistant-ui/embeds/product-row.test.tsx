import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { parseListings } from '@/lib/listing-embed'

import { ProductRow } from './product-row'

const listings = parseListings(
  JSON.stringify([
    {
      catches: ['Soldered RAM'],
      facts: ['16 GB RAM', 'OLED'],
      images: ['https://img.example/a.jpg', 'https://img.example/b.jpg'],
      kind: 'product',
      links: ['https://shop.example/a'],
      note: 'Light and quiet.',
      price: 'Rp 15.000.000',
      pros: ['Long battery', 'Bright screen'],
      title: 'Laptop A'
    },
    { kind: 'product', title: 'Laptop B' }
  ])
)

afterEach(cleanup)

describe('ProductRow', () => {
  it('renders one compact card per product, with no detail until opened', () => {
    const { container } = render(<ProductRow listings={listings} />)

    expect(container.querySelectorAll('[data-slot="aui_product-card"]')).toHaveLength(2)
    expect(screen.getByText('Laptop A')).toBeTruthy()
    expect(screen.getByText('Rp 15.000.000')).toBeTruthy()
    expect(screen.queryByText('Long battery')).toBeNull()
  })

  it('opens the detail popup from the card body, not the photo', () => {
    render(<ProductRow listings={listings} />)
    fireEvent.click(screen.getByText('Laptop A'))

    expect(screen.getByText('Long battery')).toBeTruthy()
    expect(screen.getByText('Light and quiet.')).toBeTruthy()
    expect(screen.getByText('shop.example')).toBeTruthy()
  })

  it('opens the image viewer, not the popup, from the photo', () => {
    render(<ProductRow listings={listings} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Laptop A' })[0])

    expect(screen.queryByText('Long battery')).toBeNull()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('drops a broken photo and falls through to the next one', () => {
    const { container } = render(<ProductRow listings={listings} />)

    const img = () => container.querySelector('[data-slot="aui_product-card"] img')!

    expect(img().getAttribute('src')).toBe('https://img.example/a.jpg')
    fireEvent.error(img())
    expect(img().getAttribute('src')).toBe('https://img.example/b.jpg')
  })

  it('renders no photo button for a card without images', () => {
    const { container } = render(<ProductRow listings={listings} />)

    expect(container.querySelectorAll('[data-slot="aui_product-card"]')[1].querySelector('img')).toBeNull()
  })
})
