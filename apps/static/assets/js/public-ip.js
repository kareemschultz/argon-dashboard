const PublicIPTool = {
    init() {
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.ipDetails = document.getElementById('ip-details');
        this.mapContainer = document.getElementById('map');
        this.map = null;
        this.fetchIPInfo();
    },

    async fetchIPInfo() {
        try {
            this.showLoading();

            // First, try to get the IP information using a third-party API
            const response = await fetch('https://ipapi.co/json/');
            const data = await response.json();

            this.displayIPInfo(data);
            this.initializeMap(data.latitude, data.longitude);
            this.hideLoading();
        } catch (error) {
            console.error('Error fetching IP information from third-party API:', error);

            // If third-party API fails, fall back to server-side
            try {
                const serverResponse = await fetch('/get-ip-info');
                const serverData = await serverResponse.json();

                if (serverData.error) {
                    throw new Error(serverData.error);
                }

                this.displayIPInfo(serverData);
                this.initializeMap(serverData.latitude, serverData.longitude);
            } catch (serverError) {
                this.showError('Failed to fetch IP information: ' + serverError.message);
            } finally {
                this.hideLoading();
            }
        }
    },

    displayIPInfo(data) {
        // Update all information fields
        const fields = {
            'ip-address': data.ip,
            'country': data.country_name || 'N/A',
            'region': data.region_name || 'N/A',
            'city': data.city || 'N/A',
            'postal': data.postal || 'N/A',
            'timezone': data.timezone || 'N/A',
            'isp': data.org || 'N/A',
            'org': data.org || 'N/A',
            'asn': data.asn || 'N/A',
            'hostname': data.hostname || 'N/A',
            'latitude': data.latitude || null,
            'longitude': data.longitude || null
        };

        Object.keys(fields).forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = fields[id];
            }
        });

        // Show the details container
        if (this.ipDetails) {
            this.ipDetails.style.display = 'block';
        }
    },

    initializeMap(lat, lng) {
        if (!lat || !lng || !this.mapContainer) return;

        // Clear any existing map
        this.mapContainer.innerHTML = '';

        // Initialize the map
        this.map = L.map(this.mapContainer).setView([lat, lng], 13);

        // Load and display tile layers
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }).addTo(this.map);

        // Add a marker
        L.marker([lat, lng]).addTo(this.map)
            .bindPopup('Your IP Location')
            .openPopup();
    },

    showLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'block';
        }
        if (this.ipDetails) {
            this.ipDetails.style.display = 'none';
        }
    },

    hideLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'none';
        }
    },

    showError(message) {
        this.hideLoading();
        const alertHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <span class="alert-icon"><i class="ni ni-notification-70"></i></span>
                <span class="alert-text">${message}</span>
                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `;
        
        const container = document.querySelector('.card-body');
        if (container) {
            container.insertAdjacentHTML('afterbegin', alertHtml);
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    PublicIPTool.init();
});

// Function to refresh IP information
function refreshIPInfo() {
    PublicIPTool.fetchIPInfo();
}