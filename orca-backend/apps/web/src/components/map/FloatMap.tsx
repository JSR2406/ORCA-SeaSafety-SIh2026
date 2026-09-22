'use client';

import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { cn } from '@/lib/utils';
import type { MapVisualizationData } from '@floatchat/shared-types';

interface FloatMapProps {
  data: MapVisualizationData;
  title?: string;
  className?: string;
}

export function FloatMap({ data, title, className }: FloatMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [popup, setPopup] = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Check for MapTiler key or use free tier
    const maptilerKey = process.env.NEXT_PUBLIC_MAPTILER_KEY;
    
    try {
      map.current = new maplibregl.Map({
        container: mapContainer.current,
        style: maptilerKey
          ? `https://api.maptiler.com/maps/ocean/style.json?key=${maptilerKey}`
          : 'https://demotiles.maplibre.org/style.json',
        center: data.center,
        zoom: data.zoom,
        attributionControl: false,
      });

      map.current.addControl(new maplibregl.NavigationControl(), 'top-right');
      map.current.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');

      map.current.on('load', () => {
        setMapLoaded(true);
        addFloatMarkers();
      });

      map.current.on('error', (e) => {
        console.error('Map error:', e);
        setError('Failed to load map');
      });
    } catch (err) {
      console.error('Map initialization error:', err);
      setError('Map initialization failed');
    }

    return () => {
      map.current?.remove();
      map.current = null;
      popup.current?.remove();
      popup.current = null;
    };
  }, [data.center, data.zoom]);

  const addFloatMarkers = () => {
    if (!map.current || !data.features.length) return;

    // Add source
    map.current.addSource('floats', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: data.features,
      },
    });

    // Add circle layer
    map.current.addLayer({
      id: 'floats-circle',
      type: 'circle',
      source: 'floats',
      paint: {
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          2, 4,
          6, 6,
          10, 8,
        ],
        'circle-color': [
          'interpolate',
          ['linear'],
          ['get', 'temperature_c'],
          -2, '#3b82f6',
          10, '#06b6d4',
          20, '#22c55e',
          30, '#eab308',
          35, '#ef4444',
        ],
        'circle-stroke-width': 1.5,
        'circle-stroke-color': '#ffffff',
        'circle-opacity': 0.8,
      },
    });

    // Add label layer for float IDs
    map.current.addLayer({
      id: 'floats-label',
      type: 'symbol',
      source: 'floats',
      layout: {
        'text-field': ['get', 'platform_number'],
        'text-size': 10,
        'text-font': ['Open Sans Semibold'],
        'text-anchor': 'top',
        'text-offset': [0, 1.2],
        'text-allow-overlap': true,
      },
      paint: {
        'text-color': '#1e293b',
        'text-halo-color': '#ffffff',
        'text-halo-width': 1,
      },
      minzoom: 5,
    });

    // Hover effects
    map.current.on('mouseenter', 'floats-circle', () => {
      map.current!.getCanvas().style.cursor = 'pointer';
    });

    map.current.on('mouseleave', 'floats-circle', () => {
      map.current!.getCanvas().style.cursor = '';
    });

    // Click popup
    map.current.on('click', 'floats-circle', (e) => {
      const feature = e.features?.[0];
      if (!feature) return;

      const props = feature.properties;
      const coords = feature.geometry.coordinates as [number, number];

      const content = `
        <div class="p-2 min-w-[200px]">
          <div class="font-bold text-foreground mb-1">Float ${props.platform_number}</div>
          <div class="text-sm text-muted-foreground space-y-1">
            <div>Cycle: ${props.cycle_number}</div>
            <div>Time: ${new Date(props.profile_time).toLocaleString()}</div>
            <div>Location: ${props.latitude.toFixed(3)}°, ${props.longitude.toFixed(3)}°</div>
            ${props.temperature_c !== undefined ? `<div>Temp: ${props.temperature_c.toFixed(1)}°C</div>` : ''}
            ${props.salinity_psu !== undefined ? `<div>Salinity: ${props.salinity_psu.toFixed(2)} PSU</div>` : ''}
            ${props.depth_m !== undefined ? `<div>Max Depth: ${props.depth_m.toFixed(0)}m</div>` : ''}
          </div>
        </div>
      `;

      popup.current?.remove();
      popup.current = new maplibregl.Popup({ closeButton: true, closeOnClick: true })
        .setLngLat(coords)
        .setHTML(content)
        .addTo(map.current!);
    });
  };

  // Update data when it changes
  useEffect(() => {
    if (!map.current || !mapLoaded) return;
    
    const source = map.current.getSource('floats');
    if (source && 'setData' in source) {
      source.setData({
        type: 'FeatureCollection',
        features: data.features,
      });
    }
  }, [data.features, mapLoaded]);

  if (error) {
    return (
      <div className={cn('rounded-xl border border-border bg-card flex items-center justify-center', className)}>
        <div className="p-8 text-center text-muted-foreground">
          <p>{error}</p>
          <p className="text-sm mt-2">Check MapTiler API key or network connection</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('rounded-xl border border-border overflow-hidden', className)}>
      {title && (
        <div className="px-4 py-3 border-b border-border bg-card">
          <h3 className="font-semibold text-foreground">{title}</h3>
          <p className="text-sm text-muted-foreground">{data.features.length} floats • Click for details</p>
        </div>
      )}
      <div
        ref={mapContainer}
        className="w-full h-full min-h-[400px]"
        style={{ width: '100%', height: '100%' }}
      />
      {!mapLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80 z-10">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent"></div>
        </div>
      )}
    </div>
  );
}