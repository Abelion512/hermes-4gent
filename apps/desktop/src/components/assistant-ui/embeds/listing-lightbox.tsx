'use client'

import { useEffect } from 'react'

import { ImageLightbox } from '@/components/chat/zoomable-image'
import { useImageDownload } from '@/hooks/use-image-download'
import { useI18n } from '@/i18n'

/**
 * The shared photo viewer for listing cards: the core lightbox plus ← / →
 * paging across the whole set. `openAt` null means closed.
 */
export function ListingLightbox({
  alt,
  images,
  onOpenAt,
  openAt
}: {
  alt: string
  images: string[]
  onOpenAt: (index: number | null) => void
  openAt: number | null
}) {
  const { t } = useI18n()
  const position = openAt === null ? 0 : Math.max(0, Math.min(openAt, images.length - 1))
  const { download, saving } = useImageDownload(images[position])

  // A full-size photo is the right place to go through 40 frames, and the arrow
  // keys are what hands reach for.
  useEffect(() => {
    if (openAt === null || images.length < 2) {
      return
    }

    const onKey = (event: KeyboardEvent) => {
      const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0

      if (delta !== 0) {
        event.preventDefault()
        onOpenAt((position + delta + images.length) % images.length)
      }
    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)
  }, [images.length, onOpenAt, openAt, position])

  if (images.length === 0) {
    return null
  }

  return (
    <ImageLightbox
      alt={alt}
      copy={t.desktop}
      onClick={download}
      onOpenChange={open => onOpenAt(open ? position : null)}
      open={openAt !== null}
      saving={saving}
      src={images[position]}
    />
  )
}
