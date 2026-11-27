'use client'

import { type RefObject, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from '@/i18n'
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
  // The dialog has no Trigger, so Radix has nowhere to return focus: hand it the
  // card body that opened the popup.
  const opener = useRef<HTMLElement | null>(null)

  return (
    <>
      <span
        className="my-(--paragraph-gap) -mr-1 flex w-full snap-x snap-mandatory gap-3 overflow-x-auto pr-8 pb-1 [scrollbar-width:none]"
        data-slot="aui_product-row"
      >
        {listings.map(listing => (
          <ProductCard
            key={listing.id}
            listing={listing}
            onOpen={element => {
              opener.current = element
              setOpen(listing)
            }}
          />
        ))}
      </span>

      <Dialog onOpenChange={next => !next && setOpen(null)} open={open !== null}>
        {open && <ProductDetail listing={open} returnFocusTo={opener} />}
      </Dialog>
    </>
  )
}

function ProductCard({ listing, onOpen }: { listing: Listing; onOpen: (element: HTMLElement) => void }) {
  const { t } = useI18n()
  const [broken, setBroken] = useState<string[]>([])
  const [viewAt, setViewAt] = useState<number | null>(null)
  const [picked, setPicked] = useState(0)
  const live = listing.images.filter(src => !broken.includes(src))
  const main = Math.min(picked, Math.max(live.length - 1, 0))
  const spec = productSpec(listing)

  return (
    <span className="not-prose flex w-44 shrink-0 snap-start flex-col gap-2" data-slot="aui_product-card">
      {live.length > 0 && (
        <button
          aria-label={`${t.desktop.openImage}: ${listing.address}`}
          className="block aspect-4/3 w-full cursor-zoom-in overflow-hidden rounded-2xl bg-muted/55"
          onClick={() => setViewAt(0)}
          type="button"
        >
          <img
            alt=""
            className="size-full object-cover"
            loading="lazy"
            onError={() => setBroken(prev => (prev.includes(live[0]) ? prev : [...prev, live[0]]))}
            referrerPolicy="no-referrer"
            src={live[0]}
          />
        </button>
      )}

      <button className="block min-w-0 cursor-pointer text-left" onClick={event => onOpen(event.currentTarget)} type="button">
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

function ProductDetail({
  listing,
  returnFocusTo
}: {
  listing: Listing
  returnFocusTo: RefObject<HTMLElement | null>
}) {
  const { t } = useI18n()
  const [broken, setBroken] = useState<string[]>([])
  const [viewAt, setViewAt] = useState<number | null>(null)
  const [picked, setPicked] = useState(0)
  const live = listing.images.filter(src => !broken.includes(src))
  const main = Math.min(picked, Math.max(live.length - 1, 0))
  const spec = productSpec(listing)

  return (
    <DialogContent
      bodyClassName="grid auto-rows-max grid-cols-1 content-start gap-4 overflow-y-auto sm:grid-cols-2"
      className="max-h-[85vh] sm:max-w-3xl"
      onCloseAutoFocus={event => {
        event.preventDefault()
        returnFocusTo.current?.focus()
      }}
      overlayClassName="backdrop-blur-md"
    >
      {live.length > 0 && (
        <button
          aria-label={`${t.desktop.openImage} ${main + 1}/${live.length}`}
          className="block aspect-square w-full cursor-zoom-in overflow-hidden rounded-2xl bg-muted/55"
          onClick={() => setViewAt(main)}
          type="button"
        >
          <img
            alt=""
            className="size-full object-cover"
            onError={() => setBroken(prev => (prev.includes(live[main]) ? prev : [...prev, live[main]]))}
            referrerPolicy="no-referrer"
            src={live[main]}
          />
        </button>
      )}

      <span className="flex min-w-0 flex-col gap-3">
        {live.length > 1 && (
          <span className="flex flex-wrap gap-1.5">
            {live.map((src, i) => (
              <button
                aria-label={`${i + 1}/${live.length}`}
                aria-pressed={i === main}
                className={cn(
                  'block size-16 cursor-pointer overflow-hidden rounded-2xl bg-muted/55',
                  i !== main && 'opacity-60 hover:opacity-100'
                )}
                key={src}
                onClick={() => setPicked(i)}
                type="button"
              >
                <img
                  alt=""
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
              <Button asChild key={link.url} size="xs" variant="chip">
                <ExternalLink href={link.url}>{link.label}</ExternalLink>
              </Button>
            ))}
          </span>
        )}
      </span>

      <ListingLightbox alt={listing.address} images={live} onOpenAt={setViewAt} openAt={viewAt} />
    </DialogContent>
  )
}
