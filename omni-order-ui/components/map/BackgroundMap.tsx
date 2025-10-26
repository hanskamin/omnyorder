'use client'

import { useEffect, useRef } from 'react'
import { useMapMarkers } from '@/hooks/useMapMarkers'

import { getGoogleMapsLoader } from '@/lib/googleMapsLoader'

const AUSTIN = { lat: 30.2672, lng: -97.7431 }

export default function BackgroundMap() {
  const ref = useRef<HTMLDivElement>(null)
  const { setMap } = useMapMarkers()

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
          disableDefaultUI: false,
          zoomControl: true,
          gestureHandling: 'collaborative',
          draggable: true,
          keyboardShortcuts: false,
          disableDoubleClickZoom: false,
          clickableIcons: true,
          fullscreenControl: true,
          mapTypeControl: false,
          streetViewControl: false,
        })

        setMap(google, map)

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
  }, [setMap])

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
