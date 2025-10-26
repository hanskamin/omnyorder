'use client'

import { useEffect, useRef } from 'react'

import { getGoogleMapsLoader } from '@/lib/googleMapsLoader'

const AUSTIN = { lat: 30.2672, lng: -97.7431 }

export default function BackgroundMap() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let map: google.maps.Map | undefined
    let cancelled = false

    getGoogleMapsLoader()
      .load()
      .then(async (google) => {
        if (!ref.current || cancelled) return

        const { Map } = (await google.maps.importLibrary(
          'maps',
        )) as unknown as google.maps.MapsLibrary

        map = new Map(ref.current, {
          center: AUSTIN,
          zoom: 11,
          disableDefaultUI: true,
          zoomControl: true,
          // zoomControlOptions: { position: ControlPosition.RIGHT_BOTTOM },
          gestureHandling: 'none',
          draggable: false,
          keyboardShortcuts: false,
          disableDoubleClickZoom: true,
          clickableIcons: false,
          fullscreenControl: false,
          mapTypeControl: false,
          streetViewControl: false,
        })

        navigator.geolocation?.getCurrentPosition(({ coords }) => {
          map?.setCenter({ lat: coords.latitude, lng: coords.longitude })
        })
      })
      .catch((error) => {
        console.error('Failed to initialize Google Map background', error)
      })

    return () => {
      cancelled = true
      map = undefined
    }
  }, [])

  return (
    <div
      id="background-map"
      className="map-bg"
      ref={ref}
      aria-hidden
      role="presentation"
      style={{ minHeight: '100vh', minWidth: '100vw' }}
    />
  )
}
