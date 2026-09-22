export const MapLayers = {
  TileLayer: () => null,
  WaveLayer: () => null,
  WindLayer: () => null,
  CurrentLayer: () => null,
  HazardLayer: () => null,
  TimeSlider: () => null,
};

export const WaveLayer = () => null;
export const WindLayer = () => null;
export const CurrentLayer = () => null;
export const HazardLayer = () => null;
export const RouteLayer = () => null;
export const ObservationLayer = () => null;
export const LayerControlPanel = ({ layers, onToggle }: any) => null;
export const TimeSlider = () => null;
export const MapLegend = () => null;

export interface LayerToggle {
  id: string;
  label: string;
  visible: boolean;
}
