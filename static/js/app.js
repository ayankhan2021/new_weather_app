// Global variables to store chart instances
let tempChart, humidityChart, airQualityChart;

// Chart configuration utilities
function createChartConfig(label, color, yAxisTitle) {
  return {
    type: 'line',
    data: { 
      labels: [], 
      datasets: [{
        label: label,
        data: [],
        borderColor: color.border,
        backgroundColor: color.background,
        borderWidth: 2.5,
        pointRadius: 3,
        pointHoverRadius: 5,
        pointBackgroundColor: color.border,
        tension: 0.3,
        fill: true,
        cubicInterpolationMode: 'monotone'
      }]
    },
    options: { 
      responsive: true, 
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(50, 50, 50, 0.8)',
          titleFont: { weight: 'bold', size: 14 },
          bodyFont: { size: 13 },
          padding: 10,
          cornerRadius: 6,
          displayColors: true
        },
        legend: {
          display: true,
          position: 'top',
          labels: {
            usePointStyle: true,
            padding: 15,
            font: {
              size: 12
            }
          }
        },
        title: {
          display: true,
          text: label + ' Over Time',
          font: {
            size: 16,
            weight: 'bold'
          },
          padding: {
            top: 10,
            bottom: 20
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: 'Time',
            font: {
              size: 14,
              weight: '500'
            },
            padding: {top: 10}
          },
          grid: {
            display: true,
            color: 'rgba(200, 200, 200, 0.15)'
          },
          ticks: {
            maxRotation: 45,
            minRotation: 0,
            autoSkip: true,
            maxTicksLimit: 12,
            callback: function(val, index) {
              // Display fewer x-axis labels
              const label = this.getLabelForValue(val);
              if (!label) return '';
              const timeOnly = label.split(' ')[1];
              return index % 3 === 0 ? timeOnly : '';
            }
          }
        },
        y: {
          title: {
            display: true,
            text: yAxisTitle,
            font: {
              size: 14,
              weight: '500'
            },
            padding: {right: 10}
          },
          grid: {
            display: true,
            color: 'rgba(200, 200, 200, 0.15)'
          },
          ticks: {
            precision: 1
          },
          beginAtZero: false
        }
      },
      animation: {
        duration: 1000,
        easing: 'easeOutQuart'
      },
      interaction: {
        intersect: false,
        mode: 'index'
      }
    }
  };
}

// Initialize charts
function initCharts() {
  const tempCtx = document.getElementById('tempChart').getContext('2d');
  const humidityCtx = document.getElementById('humidityChart').getContext('2d');
  const airQualityCtx = document.getElementById('airQualityChart').getContext('2d');
  
  const tempConfig = createChartConfig(
    'Temperature (°C)',
    {border: 'rgb(255, 99, 132)', background: 'rgba(255, 99, 132, 0.15)'},
    'Temperature (°C)'
  );
  
  const humidityConfig = createChartConfig(
    'Humidity (%)',
    {border: 'rgb(54, 162, 235)', background: 'rgba(54, 162, 235, 0.15)'},
    'Humidity (%)'
  );
  
  const airQualityConfig = createChartConfig(
    'Air Quality (PPM)',
    {border: 'rgb(75, 192, 192)', background: 'rgba(75, 192, 192, 0.15)'},
    'Air Quality (PPM)'
  );
  
  tempChart = new Chart(tempCtx, tempConfig);
  humidityChart = new Chart(humidityCtx, humidityConfig);
  airQualityChart = new Chart(airQualityCtx, airQualityConfig);
}

async function updateCurrentReadings() {
    try {
      const response = await axios.get('/get-latest');
      const data = response.data;
      
      document.getElementById('temperature').textContent = data.temperature?.toFixed(1) || '--';
      document.getElementById('humidity').textContent = data.humidity?.toFixed(1) || '--';
      document.getElementById('airQuality').textContent = data.air_quality?.toFixed(1) || '--';
      
      if (data.timestamp) {
        const date = new Date(data.timestamp);
        const formattedDate = date.toLocaleString('en-GB', { timeZone: 'Asia/Karachi' });
        document.getElementById('timestamp').textContent = formattedDate;
      } else {
        document.getElementById('timestamp').textContent = '--';
      }
    } catch (error) {
      console.error('Error fetching current data:', error);
      document.getElementById('temperature').textContent = 'Error';
      document.getElementById('humidity').textContent = 'Error';
      document.getElementById('airQuality').textContent = 'Error';
      document.getElementById('timestamp').textContent = 'Error';
    }
}

// Format time labels for better readability
function formatTimeLabels(timestamps) {
  return timestamps.map(timestamp => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-GB', { 
      hour: '2-digit', 
      minute: '2-digit'
    });
  });
}

// Update historical data charts
async function updateCharts() {
  try {
    const response = await axios.get('/get-history');
    const data = response.data;

    console.log("Current time:", new Date().toLocaleTimeString());
    console.log("API response times:", data.timestamps.map(t => new Date(t).toLocaleTimeString()));
    console.log("Time difference:", 
      (new Date() - new Date(data.timestamps[data.timestamps.length-1]))/60000, "minutes");
    
    // Enhance data analysis for better chart visualization
    const formattedLabels = formatTimeLabels(data.timestamps);
    
    // Calculate min/max for better y-axis scaling
    if (data.temperatures && data.temperatures.length > 0) {
      const tempMin = Math.floor(Math.min(...data.temperatures)) - 1;
      const tempMax = Math.ceil(Math.max(...data.temperatures)) + 1;
      
      tempChart.options.scales.y.min = tempMin;
      tempChart.options.scales.y.max = tempMax;
      
      // Add data analysis annotation
      const tempAvg = data.temperatures.reduce((sum, val) => sum + val, 0) / data.temperatures.length;
      tempChart.data.datasets[0].label = `Temperature (°C) - Avg: ${tempAvg.toFixed(1)}°C`;
      
      // Update chart data
      tempChart.data.labels = data.timestamps;
      tempChart.data.datasets[0].data = data.temperatures;
      tempChart.update();
    }
    
    // Update humidity chart with improved scaling
    if (data.timestamps && data.humidities) {
      const humidityMin = Math.max(0, Math.floor(Math.min(...data.humidities)) - 5);
      const humidityMax = Math.min(100, Math.ceil(Math.max(...data.humidities)) + 5);
      
      humidityChart.options.scales.y.min = humidityMin;
      humidityChart.options.scales.y.max = humidityMax;
      
      const humidityAvg = data.humidities.reduce((sum, val) => sum + val, 0) / data.humidities.length;
      humidityChart.data.datasets[0].label = `Humidity (%) - Avg: ${humidityAvg.toFixed(1)}%`;
      
      humidityChart.data.labels = data.timestamps;
      humidityChart.data.datasets[0].data = data.humidities;
      humidityChart.update();
    }
    
    // Update air quality chart with improved scaling
    if (data.timestamps && data.air_qualities) {
      const aqMin = Math.max(0, Math.floor(Math.min(...data.air_qualities)) - 10);
      const aqMax = Math.ceil(Math.max(...data.air_qualities)) + 10;
      
      airQualityChart.options.scales.y.min = aqMin;
      airQualityChart.options.scales.y.max = aqMax;
      
      const aqAvg = data.air_qualities.reduce((sum, val) => sum + val, 0) / data.air_qualities.length;
      airQualityChart.data.datasets[0].label = `Air Quality (PPM) - Avg: ${aqAvg.toFixed(1)}`;
      
      airQualityChart.data.labels = data.timestamps;
      airQualityChart.data.datasets[0].data = data.air_qualities;
      airQualityChart.update();
    }
  } catch (error) {
    console.error('Error fetching historical data:', error);
  }
}
      
// Refresh all data
async function refreshData() {
  await updateCurrentReadings();
  await updateCharts();
}

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
  // Apply theme to page
  document.body.classList.add('charts-initialized');
  
  initCharts();
  refreshData();
  
  // Set up auto-refresh every 30 seconds
  setInterval(refreshData, 30000);
  
  // Manual refresh button with animation
  const refreshBtn = document.getElementById('refreshBtn');
  refreshBtn.addEventListener('click', async () => {
    refreshBtn.classList.add('rotating');
    await refreshData();
    setTimeout(() => refreshBtn.classList.remove('rotating'), 1000);
  });
});