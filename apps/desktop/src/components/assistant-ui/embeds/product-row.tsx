'use client'

import { useState } from 'react'

import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { ExternalLink } from '@/lib/external-link'
import { type Listing } from '@/lib/listing-embed'
import { cn } from '@/lib/utils'

import { ListingLightbox } from './listing-lightbox'

const TEXT_CLASS = 'text-[length:var(--conversation-text-font-size)]'
const META_CLASS = 'text-[length:var(--conversation-tool-font-size)]'

/** One-line spec under the name: size first, then the first facts. */
function productSpec(listing: Listing): string {
  return [listing.size, ...listing.facts].filter(Boolean).join(' · ')
}

/**
 * ```listing with `"kind":"product"` — compact cards in ONE horizontal row.
 *
 * Only this row scrolls; the transcript keeps flowing down. Cards are
 * borderless (spacing and type carry the hierarchy, no panel and no
 * card-in-card). Clicking the card body opens one detail popup; clicking the
 * photo opens the image viewer instead — two targets, no separate Detail
 * button.
 */
export function ProductRow({ listings }: { listings: Listing[] }) {
  const [open, setOpen] = useState<Listing | null>(null)

  return (
    <>
      <span
        className="my-(--paragraph-gap) -mr-1 flex w-full snap-x snap-mandatory gap-3 overflow-x-auto pr-8 pb-1 [scrollbar-width:none]"
        data-slot="aui_product-row"
      >
        {listings.map(listing => (
          <ProductCard key={listing.id} listing={listing} onOpen={() => setOpen(listing)} />
        ))}
      </span>

      <Dialog onOpenChange={next => !next && setOpen(null)} open={open !== null}>
        {open && <ProductDetail listing={open} />}
      </Dialog>
    </>
  )
}

function ProductCard({ listing, onOpen }: { listing: Listing; onOpen: () => void }) {
  const [broken, setBroken] = useState<string[]>([])
  const [viewAt, setViewAt] = useState<number | null>(null)
  const live = listing.images.filter(src => !broken.includes(src))
  const spec = productSpec(listing)

  return (
    <span className="not-prose flex w-44 shrink-0 snap-start flex-col gap-2" data-slot="aui_product-card">
      {live.length > 0 && (
        <button
          aria-label={listing.address}
          className="block aspect-4/3 w-full cursor-zoom-in overflow-hidden rounded-2xl bg-muted/55"
          onClick={() => setViewAt(0)}
          type="button"
        >
          <img
            alt={listing.address}
            className="size-full object-cover"
            loading="lazy"
            onError={() => setBroken(prev => (prev.includes(live[0]) ? prev : [...prev, live[0]]))}
            referrerPolicy="no-referrer"
            src={live[0]}
          />
        </button>
      )}

      <button className="block min-w-0 cursor-pointer text-left" onClick={onOpen} type="button">
        <span className={cn(TEXT_CLASS, 'block truncate font-medium text-foreground')}>{listing.address}</span>
        {listing.price && (
          <span className={cn(TEXT_CLASS, 'block tabular-nums text-foreground')}>{listing.price}</span>
        )}
        {spec && <span className={cn(META_CLASS, 'block truncate text-muted-foreground')}>{spec}</span>}
      </button>

      <ListingLightbox alt={listing.address} images={live} onOpenAt={setViewAt} openAt={viewAt} />
    </span>
  )
}

function ProductDetail({ listing }: { listing: Listing }) {
  const [broken, setBroken] = useState<string[]>([])
  const [viewAt, setViewAt] = useState<number | null>(null)
  const live = listing.images.filter(src => !broken.includes(src))
  const spec = productSpec(listing)

  return (
    <DialogContent bodyClassName="gap-3 overflow-y-auto" className="max-h-[85vh]">
      {live.length > 0 && (
        <span className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]">
          {live.map((src, index) => (
            <button
              className={cn(
                'block shrink-0 cursor-zoom-in overflow-hidden rounded-2xl bg-muted/55',
                index === 0 ? 'aspect-4/3 w-full' : 'aspect-4/3 w-24'
              )}
              key={src}
              onClick={() => setViewAt(index)}
              type="button"
            >
              <img
                alt={listing.address}
                className="size-full object-cover"
                onError={() => setBroken(prev => (prev.includes(src) ? prev : [...prev, src]))}
                referrerPolicy="no-referrer"
                src={src}
              />
            </button>
          ))}
        </span>
      )}

      <span className="flex flex-wrap items-baseline justify-between gap-x-3">
        <DialogTitle>{listing.address}</DialogTitle>
        {listing.price && <span className={cn(TEXT_CLASS, 'font-medium tabular-nums')}>{listing.price}</span>}
      </span>

      {spec ? (
        <DialogDescription className={cn(META_CLASS, 'tabular-nums')}>{spec}</DialogDescription>
      ) : (
        <DialogDescription className="sr-only">{listing.address}</DialogDescription>
      )}

      {listing.note && <span className={cn(TEXT_CLASS, 'leading-relaxed text-foreground/80')}>{listing.note}</span>}

      {listing.pros.length > 0 && (
        <ul className={cn(TEXT_CLASS, 'list-disc space-y-0.5 pl-5 text-foreground/80')}>
          {listing.pros.map(pro => (
            <li key={pro}>{pro}</li>
          ))}
        </ul>
      )}

      {listing.catches.length > 0 && (
        <span className={cn(META_CLASS, 'text-muted-foreground')}>{listing.catches.join(' · ')}</span>
      )}

      {listing.links.length > 0 && (
        <span className={cn(META_CLASS, 'flex flex-wrap gap-x-3 gap-y-1')}>
          {listing.links.map(link => (
            <ExternalLink href={link.url} key={link.url}>
              {link.label}
            </ExternalLink>
          ))}
        </span>
      )}

      <ListingLightbox alt={listing.address} images={live} onOpenAt={setViewAt} openAt={viewAt} />
    </DialogContent>
  )
}
