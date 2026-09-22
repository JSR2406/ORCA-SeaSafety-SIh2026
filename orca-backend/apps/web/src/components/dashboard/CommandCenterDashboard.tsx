"use client";

import { useState, useEffect } from "react";
import { MapContainer } from "react-leaflet";
import { MapLayers, WaveLayer, WindLayer, CurrentLayer, HazardLayer, RouteLayer, ObservationLayer, LayerControlPanel, TimeSlider, MapLegend, LayerToggle } from "./MapLayers";

interface DashboardMetrics {
  activeFloats: number;
  totalProfiles: number;
  recentObservations: number;
  activeHazards: number;
  activeRoutes: number;
  dataFreshness: string;
  systemStatus: "healthy" | "degraded" | "warning";
  lastUpdate: string;
}

export function CommandCenterDashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics>({
    activeFloats: 16,
    totalProfiles: 1184,
    recentObservations: 35520,
    activeHazards: 3,
    activeRoutes: 2,
    dataFreshness: "6 hours",
    systemStatus: "healthy",
    lastUpdate: "2026-08-28 14:30 UTC",
  });
  
  const [mapLayers, setMapLayers] = useState<LayerToggle[]>([
    { id: "observations", label: "ARGO Observations", visible: true },
    { id: "waves", label: "Wave Height", visible: false },
    { id: "wind", label: "Wind Speed", visible: false },
    { id: "currents", label: "Currents", visible: false },
    { id: "hazards", label: "Hazards & Alerts", visible: true },
    { id: "geofences", label: "Geofences (MPA/EEZ)", visible: false },
    { id: "routes", label: "Route Analysis", visible: false },
  ]);
  
  const [mapCenter, setMapCenter] = useState<[number, number]>([15.0, 75.0]);
  const [mapZoom, setMapZoom] = useState(5);
  const [currentTime, setCurrentTime] = useState(new Date().toISOString());
  const [playing, setPlaying] = useState(false);
  
  const handleLayerToggle = (id: string, visible: boolean) => {
    setMapLayers(prev => prev.map(l => l.id === id ? { ...l, visible } : l));
  };
  
  // Mock data for demo
  const mockObservations = [
    { lat: 12.5, lon: 74.8, float_id: 12345, profile_id: 678, date: "2026-08-27", temperature: 28.5, salinity: 35.2 },
    { lat: 18.2, lon: 72.1, float_id: 23456, profile_id: 679, date: "2026-08-27", temperature: 27.8, salinity: 35.4 },
    { lat: 10.8, lon: 76.3, float_id: 34567, profile_id: 680, date: "2026-08-26", temperature: 29.1, salinity: 34.9 },
    { lat: 15.3, lon: 73.2, float_id: 45678, profile_id: 681, date: "2026-08-26", temperature: 28.2, salinity: 35.1 },
  ];
  
  const mockRoute = [
    { lat: 19.0760, lon: 72.8777 }, // Mumbai
    { lat: 17.5, lon: 73.0 },
    { lat: 15.3, lon: 73.5 },
    { lat: 13.0, lon: 74.0 },
    { lat: 10.5, lon: 74.5 },
  ];
  
  const mockHazards = [
    { 
      id: "haz-1", 
      type: "cyclone", 
      severity: "moderate", 
      location: { lat: 16.5, lon: 71.2 },
      description: "Cyclone warning - System moving NW at 15 km/h"
    },
    { 
      id: "haz-2", 
      type: "storm", 
      severity: "high", 
      location: { lat: 13.8, lon: 74.5 },
      description: "Severe storm with gusts up to 90 km/h"
    },
  ];
  
  const mockGeofences = [
    {
      id: "gf-1",
      name: "Arabian Sea MPA",
      type: "Marine Protected Area",
      coordinates: [[[61, 18], [65, 18], [65, 22], [61, 22], [61, 18]]],
    },
  ];
  
  return (
    <div className="h-screen w-full bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg flex items-center justify-center text-white font-bold">
              ORCA
            </div>
            <h1 className="text-xl font-semibold text-gray-900">Marine Intelligence Platform</h1>
            <span className={`px-2 py-1 text-xs rounded-full ${
              metrics.systemStatus === "healthy" ? "bg-green-100 text-green-700" :
              metrics.systemStatus === "degraded" ? "bg-yellow-100 text-yellow-700" :
              "bg-red-100 text-red-700"
            }`}>
              {metrics.systemStatus.toUpperCase()}
            </span>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-xs text-gray-500">Last Update</div>
              <div className="text-sm font-mono text-gray-900">{metrics.lastUpdate}</div>
            </div>
            <div className="w-px h-8 bg-gray-200"></div>
            <div className="text-right">
              <div className="text-xs text-gray-500">Data Freshness</div>
              <div className="text-sm font-mono text-gray-900">{metrics.dataFreshness}</div>
            </div>
          </div>
        </div>
      </header>
      
      {/* Metrics Bar */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-6 gap-4">
          <MetricCard 
            label="Active Floats" 
            value={metrics.activeFloats} 
            icon="🛰️"
            trend="+2 this week"
            trendUp={true}
          />
          <MetricCard 
            label="Total Profiles" 
            value={metrics.totalProfiles.toLocaleString()} 
            icon="📊"
            trend="+45 today"
            trendUp={true}
          />
          <MetricCard 
            label="Observations" 
            value={metrics.recentObservations.toLocaleString()} 
            icon="📈"
            trend="+1,240 today"
            trendUp={true}
          />
          <MetricCard 
            label="Active Hazards" 
            value={metrics.activeHazards} 
            icon="⚠️"
            trend={metrics.activeHazards > 0 ? "Active alerts" : "No alerts"}
            trendUp={metrics.activeHazards === 0}
            alert={metrics.activeHazards > 0}
          />
          <MetricCard 
            label="Active Routes" 
            value={metrics.activeRoutes} 
            icon="🗺️"
            trend="2 planned"
          />
          <MetricCard 
            label="Data Freshness" 
            value={metrics.dataFreshness} 
            icon="🕐"
            trend="Updated 15 min ago"
          />
        </div>
      </div>
      
      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-72 bg-white border-r border-gray-200 flex flex-col">
          {/* Layer Control */}
          <LayerControlPanel 
            layers={mapLayers}
            onToggle={(id, visible) => handleLayerToggle(id, visible)}
          />
          
          <div className="p-4 border-t border-gray-200">
            <div className="font-semibold text-sm mb-2">Quick Actions</div>
            <div className="space-y-2">
              <button className="w-full px-3 py-2 text-left bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors text-sm">
                🔍 New Route Analysis
              </button>
              <button className="w-full px-3 py-2 text-left bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-colors text-sm">
                ⚠️ Hazard Assessment
              </button>
              <button className="w-full px-3 py-2 text-left bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-colors text-sm">
                📈 Scenario Projection
              </button>
              <button className="w-full px-3 py-2 text-left bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 transition-colors text-sm">
                📋 Export Data
              </button>
            </div>
          </div>
          
          <div className="p-4 border-t border-gray-200">
            <div className="font-semibold text-sm mb-2">Recent Queries</div>
            <div className="space-y-2 text-sm text-gray-600">
              <div className="p-2 bg-gray-50 rounded-lg">
                <div className="font-medium">Temperature in Arabian Sea</div>
                <div className="text-xs text-gray-500">2 min ago • en-IN</div>
              </div>
              <div className="p-2 bg-gray-50 rounded-lg">
                <div className="font-medium">Mumbai to Goa Route Safety</div>
                <div className="text-xs text-gray-500">15 min ago • hi-IN</div>
              </div>
              <div className="p-2 bg-gray-50 rounded-lg">
                <div className="font-medium">Cyclone Alert - Bay of Bengal</div>
                <div className="text-xs text-gray-500">1 hour ago • en-IN</div>
              </div>
            </div>
          </div>
          
          <div className="p-4 border-t border-gray-200">
            <div className="font-semibold text-sm mb-2">System Status</div>
            <div className="space-y-1 text-xs text-gray-600">
              <div className="flex justify-between">
                <span>API Gateway</span>
                <span className="text-green-600">● Online</span>
              </div>
              <div className="flex justify-between">
                <span>Database</span>
                <span className="text-green-600">● Connected</span>
              </div>
              <div className="flex justify-between">
                <span>ARGO Pipeline</span>
                <span className="text-green-600">● Running</span>
              </div>
              <div className="flex justify-between">
                <span>Voice Services</span>
                <span className="text-green-600">● Ready</span>
              </div>
            </div>
          </div>
        </aside>
        
        {/* Main Map */}
        <main className="flex-1 relative">
          <MapContainer
            center={mapCenter}
            zoom={mapZoom}
            onMoveEnd={(e) => {
              setMapCenter([e.target.getCenter().lat, e.target.getCenter().lng]);
              setMapZoom(e.target.getZoom());
            }}
            className="h-full w-full"
          >
            <MapLayers.TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            
            {mapLayers.find(l => l.id === "observations" && l.visible) && (
              <ObservationLayer data={mockObservations} />
            )}
            
            {mapLayers.find(l => l.id === "waves" && l.visible) && (
              <MapLayers.WaveLayer data={mockObservations.map(o => ({...o, wave_height: 1.5 + Math.random() * 1.5, wave_period: 6 + Math.random() * 4, wave_direction: Math.random() * 360}))} />
            )}
            
            {mapLayers.find(l => l.id === "wind" && l.visible) && (
              <MapLayers.WindLayer data={mockObservations.map(o => ({...o, wind_speed: 5 + Math.random() * 15, wind_direction: Math.random() * 360}))} />
            )}
            
            {mapLayers.find(l => l.id === "currents" && l.visible) && (
              <MapLayers.CurrentLayer data={mockObservations.map(o => ({...o, current_speed: 0.2 + Math.random() * 0.8, current_direction: Math.random() * 360}))} />
            )}
            
            {mapLayers.find(l => l.id === "hazards" && l.visible) && (
              <MapLayers.HazardLayer data={mockHazards} />
            )}
            
            {mapLayers.find(l => l.id === "geofences" && l.visible) && (
              <MapLayers.GeofenceLayer data={mockGeofences} />
            )}
            
            {mapLayers.find(l => l.id === "routes" && l.visible) && (
              <RouteLayer route={mockRoute} riskScore={0.35} />
            )}
            
            {/* Map Legend */}
            <MapLegend layers={[
              { id: "observations", label: "ARGO Floats", color: "#0077b6", type: "circle" },
              { id: "hazards", label: "Hazards", color: "#f4a261", type: "circle" },
              { id: "routes", label: "Routes", color: "#0077b6", type: "line" },
              { id: "geofences", label: "Geofences", color: "#e76f51", type: "polygon" },
            ]} />
            
            {/* Layer Control Panel */}
            <LayerControlPanel 
              layers={mapLayers}
              onToggle={handleLayerToggle}
            />
            
            {/* Time Slider */}
            <MapLayers.TimeSlider
              timeRange={{ start: "2024-01-01", end: "2024-12-31" }}
              currentTime={currentTime}
              onTimeChange={setCurrentTime}
              playing={playing}
              onPlayToggle={() => setPlaying(!playing)}
            />
          </MapContainer>
        </main>
      </div>
    </div>
  );
}

function MetricCard({ 
  label, 
  value, 
  icon, 
  trend, 
  trendUp = true, 
  alert = false 
}: { 
  label: string; 
  value: string | number; 
  icon: string; 
  trend: string; 
  trendUp?: boolean; 
  alert?: boolean; 
}) {
  return (
    <div className={`p-3 rounded-lg border ${alert ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <div>
            <div className="text-xs text-gray-500">{label}</div>
            <div className="text-2xl font-bold text-gray-900">{value}</div>
          </div>
        </div>
        <div className={`text-xs ${trendUp ? "text-green-600" : "text-red-600"}`}>
          {trendUp ? "↑ " : "↓ "}{trend}
        </div>
      </div>
    </div>
  );
}

export default CommandCenterDashboard;