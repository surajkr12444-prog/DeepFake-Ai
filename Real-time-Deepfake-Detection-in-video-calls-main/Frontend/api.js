// DeepShield — REST API Client Module

const ApiClient = (() => {
  async function request(url, options = {}) {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        },
        ...options
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API HTTP ${response.status}: ${errorText || response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      console.warn(`[ApiClient] Request to ${url} failed:`, err);
      throw err;
    }
  }

  return {
    async checkHealth() {
      return await request(Config.ENDPOINTS.HEALTH);
    },

    async createSession(sensitivityThreshold = 60.0) {
      return await request(Config.ENDPOINTS.SESSIONS, {
        method: 'POST',
        body: JSON.stringify({
          client_name: 'DeepShield-Web',
          sensitivity_threshold: sensitivityThreshold
        })
      });
    },

    async getSession(sessionId) {
      return await request(`${Config.ENDPOINTS.SESSIONS}/${sessionId}`);
    },

    async deleteSession(sessionId) {
      return await request(`${Config.ENDPOINTS.SESSIONS}/${sessionId}`, {
        method: 'DELETE'
      });
    },

    async getStatus() {
      return await request(Config.ENDPOINTS.STATUS);
    },

    async getStats() {
      return await request(Config.ENDPOINTS.STATS);
    },

    async getLogs(limit = 8) {
      return await request(`${Config.ENDPOINTS.LOGS}?limit=${limit}`);
    },

    async updateSettings(similarityThreshold) {
      return await request(Config.ENDPOINTS.SETTINGS, {
        method: 'POST',
        body: JSON.stringify({ similarity_threshold: similarityThreshold })
      });
    },

    async enrollFace(imageBase64) {
      return await request(Config.ENDPOINTS.ENROLL, {
        method: 'POST',
        body: JSON.stringify({
          image_base64: imageBase64,
          name: 'caller_profile'
        })
      });
    },

    async detectSingleFrame(imageBase64, threshold = 0.60) {
      return await request(Config.ENDPOINTS.DETECT, {
        method: 'POST',
        body: JSON.stringify({
          image_base64: imageBase64,
          threshold: threshold
        })
      });
    },

    async predictVoiceFile(fileBlob, filename = 'voice_sample.wav') {
      const formData = new FormData();
      formData.append('file', fileBlob, filename);
      const response = await fetch(Config.ENDPOINTS.VOICE_PREDICT, {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Voice Prediction Failed (${response.status}): ${errorText}`);
      }
      return await response.json();
    }
  };
})();


window.ApiClient = ApiClient;
