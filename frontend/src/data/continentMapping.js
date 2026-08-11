// Continent center coordinates and zoom framing for 3D camera fly-to
export const CONTINENT_CENTERS = {
  'North America': { lat: 40, lng: -100, altitude: 2.2 },
  'South America': { lat: -15, lng: -60, altitude: 2.2 },
  'Europe': { lat: 50, lng: 15, altitude: 1.8 },
  'Africa': { lat: 0, lng: 20, altitude: 2.2 },
  'Asia': { lat: 35, lng: 90, altitude: 2.4 },
  'Oceania': { lat: -25, lng: 135, altitude: 2.2 },
  'Antarctica': { lat: -80, lng: 0, altitude: 2.5 },
};

// Default camera position for World View
export const WORLD_CENTER = { lat: 20, lng: 0, altitude: 2.5 };

// ISO 3166-1 Numeric ID to Continent Mapping
const ISO_NUMERIC_TO_CONTINENT = {
  // North America
  '840': 'North America', // USA
  '124': 'North America', // Canada
  '484': 'North America', // Mexico
  '192': 'North America', // Cuba
  '332': 'North America', // Haiti
  '214': 'North America', // Dominican Republic
  '340': 'North America', // Honduras
  '320': 'North America', // Guatemala
  '558': 'North America', // Nicaragua
  '188': 'North America', // Costa Rica
  '591': 'North America', // Panama
  '084': 'North America', // Belize
  '222': 'North America', // El Salvador
  '044': 'North America', // Bahamas

  // South America
  '076': 'South America', // Brazil
  '032': 'South America', // Argentina
  '170': 'South America', // Colombia
  '152': 'South America', // Chile
  '604': 'South America', // Peru
  '862': 'South America', // Venezuela
  '218': 'South America', // Ecuador
  '068': 'South America', // Bolivia
  '600': 'South America', // Paraguay
  '858': 'South America', // Uruguay
  '328': 'South America', // Guyana
  '740': 'South America', // Suriname

  // Europe
  '250': 'Europe', // France
  '276': 'Europe', // Germany
  '826': 'Europe', // UK
  '380': 'Europe', // Italy
  '724': 'Europe', // Spain
  '804': 'Europe', // Ukraine
  '643': 'Europe', // Russia
  '528': 'Europe', // Netherlands
  '056': 'Europe', // Belgium
  '756': 'Europe', // Switzerland
  '752': 'Europe', // Sweden
  '578': 'Europe', // Norway
  '246': 'Europe', // Finland
  '620': 'Europe', // Portugal
  '300': 'Europe', // Greece
  '616': 'Europe', // Poland
  '642': 'Europe', // Romania
  '040': 'Europe', // Austria
  '050': 'Europe', // Bangladesh -> Asia (override below if needed)
  '100': 'Europe', // Bulgaria
  '191': 'Europe', // Croatia
  '203': 'Europe', // Czechia
  '208': 'Europe', // Denmark
  '348': 'Europe', // Hungary
  '372': 'Europe', // Ireland
  '428': 'Europe', // Latvia
  '440': 'Europe', // Lithuania
  '498': 'Europe', // Moldova
  '688': 'Europe', // Serbia
  '703': 'Europe', // Slovakia
  '705': 'Europe', // Slovenia
  '112': 'Europe', // Belarus

  // Africa
  '710': 'Africa', // South Africa
  '818': 'Africa', // Egypt
  '566': 'Africa', // Nigeria
  '404': 'Africa', // Kenya
  '231': 'Africa', // Ethiopia
  '012': 'Africa', // Algeria
  '504': 'Africa', // Morocco
  '024': 'Africa', // Angola
  '120': 'Africa', // Cameroon
  '180': 'Africa', // DR Congo
  '262': 'Africa', // Djibouti
  '232': 'Africa', // Eritrea
  '288': 'Africa', // Ghana
  '434': 'Africa', // Libya
  '450': 'Africa', // Madagascar
  '466': 'Africa', // Mali
  '508': 'Africa', // Mozambique
  '516': 'Africa', // Namibia
  '562': 'Africa', // Niger
  '686': 'Africa', // Senegal
  '706': 'Africa', // Somalia
  '728': 'Africa', // South Sudan
  '729': 'Africa', // Sudan
  '834': 'Africa', // Tanzania
  '788': 'Africa', // Tunisia
  '800': 'Africa', // Uganda
  '894': 'Africa', // Zambia
  '716': 'Africa', // Zimbabwe

  // Asia
  '156': 'Asia', // China
  '356': 'Asia', // India
  '392': 'Asia', // Japan
  '410': 'Asia', // South Korea
  '408': 'Asia', // North Korea
  '360': 'Asia', // Indonesia
  '682': 'Asia', // Saudi Arabia
  '364': 'Asia', // Iran
  '792': 'Asia', // Turkey
  '586': 'Asia', // Pakistan
  '050': 'Asia', // Bangladesh
  '704': 'Asia', // Vietnam
  '764': 'Asia', // Thailand
  '458': 'Asia', // Malaysia
  '608': 'Asia', // Philippines
  '702': 'Asia', // Singapore
  '376': 'Asia', // Israel
  '368': 'Asia', // Iraq
  '760': 'Asia', // Syria
  '860': 'Asia', // Uzbekistan
  '398': 'Asia', // Kazakhstan
  '004': 'Asia', // Afghanistan
  '524': 'Asia', // Nepal
  '144': 'Asia', // Sri Lanka
  '418': 'Asia', // Laos
  '116': 'Asia', // Cambodia
  '104': 'Asia', // Myanmar
  '784': 'Asia', // UAE
  '634': 'Asia', // Qatar

  // Oceania
  '036': 'Oceania', // Australia
  '554': 'Oceania', // New Zealand
  '598': 'Oceania', // Papua New Guinea
  '242': 'Oceania', // Fiji
  '090': 'Oceania', // Solomon Islands

  // Antarctica
  '010': 'Antarctica',
};

// Helper function to resolve continent from GeoJSON feature properties/ID
export function getContinentForFeature(feature) {
  if (!feature) return 'Unknown';
  
  const idStr = String(feature.id || '').padStart(3, '0');
  if (ISO_NUMERIC_TO_CONTINENT[idStr]) {
    return ISO_NUMERIC_TO_CONTINENT[idStr];
  }
  
  const name = feature.properties?.name || '';
  // Name fallback mapping if numeric ID isn't matched
  if (/United States|Canada|Mexico|Cuba|Panama|Costa Rica|Jamaica|Guatemala/i.test(name)) return 'North America';
  if (/Brazil|Argentina|Colombia|Chile|Peru|Venezuela|Ecuador|Bolivia/i.test(name)) return 'South America';
  if (/France|Germany|United Kingdom|Italy|Spain|Ukraine|Russia|Poland|Netherlands|Sweden|Norway|Finland/i.test(name)) return 'Europe';
  if (/Egypt|Nigeria|South Africa|Kenya|Ethiopia|Algeria|Morocco|Ghana|Sudan/i.test(name)) return 'Africa';
  if (/China|India|Japan|South Korea|Indonesia|Saudi Arabia|Iran|Turkey|Pakistan|Vietnam|Thailand/i.test(name)) return 'Asia';
  if (/Australia|New Zealand|Papua New Guinea|Fiji/i.test(name)) return 'Oceania';
  if (/Antarctica/i.test(name)) return 'Antarctica';

  return 'Asia'; // Default fallback
}
