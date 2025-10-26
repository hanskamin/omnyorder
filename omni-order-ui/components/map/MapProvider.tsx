'use client'

import { createContext, useMemo, useRef, useState } from 'react'

export type MarkerId = string

type AddMarkerParams = {
  id?: MarkerId
  position: google.maps.LatLngLiteral
  options?: google.maps.MarkerOptions
}

export type MapMarkersContextValue = {
  ready: boolean
  setMap: (g: typeof google, m: google.maps.Map) => void
  addMarker: (params: AddMarkerParams) => MarkerId
  removeMarker: (id: MarkerId) => void
  clearMarkers: () => void
  getMarker: (id: MarkerId) => google.maps.Marker | undefined
  getMap: () => google.maps.Map | null
  getGoogle: () => (typeof google) | null
}

export const MapMarkersContext = createContext<MapMarkersContextValue | null>(null)

function generateMarkerId() {
  return `m_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`
}

export default function MapProvider({ children }: { children: React.ReactNode }) {
  const googleRef = useRef<typeof google | null>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markersRef = useRef<Map<MarkerId, google.maps.Marker>>(new Map())
  const pendingRef = useRef<AddMarkerParams[]>([])
  const [ready, setReady] = useState(false)

  const setMap = (g: typeof google, m: google.maps.Map) => {
    googleRef.current = g
    mapRef.current = m
    setReady(true)

    if (pendingRef.current.length > 0) {
      for (const job of pendingRef.current) {
        internalAddOrUpdateMarker(job)
      }
      pendingRef.current = []
    }
  }

  const internalAddOrUpdateMarker = (params: AddMarkerParams): MarkerId => {
    const id = params.id ?? generateMarkerId()
    const existing = markersRef.current.get(id)

    if (existing) {
      existing.setOptions({ ...(params.options ?? {}), position: params.position, map: mapRef.current ?? undefined })
      markersRef.current.set(id, existing)
      return id
    }

    if (!googleRef.current || !mapRef.current) {
      // Shouldn't happen when called from public addMarker because we guard, but keep for safety
      pendingRef.current.push({ ...params, id })
      return id
    }

    const marker = new google.maps.Marker({
      position: params.position,
      map: mapRef.current,
      ...(params.options ?? {}),
    })
    markersRef.current.set(id, marker)
    return id
  }

  const addMarker = (params: AddMarkerParams): MarkerId => {
    if (!ready) {
      const id = params.id ?? generateMarkerId()
      pendingRef.current.push({ ...params, id })
      return id
    }
    return internalAddOrUpdateMarker(params)
  }

  const removeMarker = (id: MarkerId) => {
    const marker = markersRef.current.get(id)
    if (marker) {
      marker.setMap(null)
      markersRef.current.delete(id)
    }
    // Also remove pending if queued
    pendingRef.current = pendingRef.current.filter((p) => p.id !== id)
  }

  const clearMarkers = () => {
    markersRef.current.forEach((marker) => marker.setMap(null))
    markersRef.current.clear()
    pendingRef.current = []
  }

  const getMarker = (id: MarkerId) => markersRef.current.get(id)

  const value: MapMarkersContextValue = useMemo(
    () => ({
      ready,
      setMap,
      addMarker,
      removeMarker,
      clearMarkers,
      getMarker,
      getMap: () => mapRef.current,
      getGoogle: () => googleRef.current,
    }),
    [ready],
  )

  return <MapMarkersContext.Provider value={value}>{children}</MapMarkersContext.Provider>
}


