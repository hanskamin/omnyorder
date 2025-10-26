import { Loader } from '@googlemaps/js-api-loader'

let loader: Loader | null = null

export const getGoogleMapsLoader = () =>
  loader ??= new Loader({
    apiKey: getApiKey(),
    version: 'weekly',
  })

const getApiKey = () => {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
  if (!apiKey) {
    throw new Error('Missing NEXT_PUBLIC_GOOGLE_MAPS_API_KEY environment variable.')
  }
  return apiKey
}
