'use client'

import { useContext } from 'react'
import { MapMarkersContext } from '@/components/map/MapProvider'

export function useMapMarkers() {
  const ctx = useContext(MapMarkersContext)
  if (!ctx) {
    throw new Error('useMapMarkers must be used within a MapProvider')
  }
  return ctx
}


