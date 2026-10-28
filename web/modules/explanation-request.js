// A latest-request slot. Cancellation plus identity checks protects against late responses.
class ExplanationRequest {
  constructor() { this.current = null; }
  cancel() {
    this.current?.abort();
    this.current = null;
  }
  async fetch(url) {
    this.cancel();
    const controller = new AbortController();
    this.current = controller;
    try {
      const response = await fetch(url, {signal: controller.signal});
      if (!response.ok) {
        const body = await response.json();
        throw Error(body.detail || 'Explanation request failed.');
      }
      const blob = await response.blob();
      return this.current === controller ? blob : null;
    } catch (error) {
      if (this.current !== controller || error.name === 'AbortError') return null;
      throw error;
    }
  }
}
if (typeof module !== 'undefined') module.exports = ExplanationRequest;
