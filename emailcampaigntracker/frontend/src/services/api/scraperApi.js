import { httpClient } from './httpClient';

export function triggerScrape() {
  return httpClient.post(`scrape`);
}

export function fetchScraperStatus({ signal } = {}) {
  return httpClient.get(`scraper-status?t=${Date.now()}`, { signal });
}

