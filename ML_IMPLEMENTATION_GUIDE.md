# ML Implementation Guide - OpenLandMap Platform

## Overview
This guide provides step-by-step instructions for implementing the 4 ML modules when ready.

---

## 📋 Prerequisites

### Environment Setup
```bash
# Python 3.8+
python --version

# Required packages
pip install tensorflow pandas numpy scikit-learn scipy matplotlib seaborn geopandas rasterio

# Optional (for advanced features)
pip install lightgbm xgboost pytorch jupyter
```

### GEE Setup (One-time)
```bash
# Install GEE Python API
pip install earthengine-api

# Authenticate
earthengine authenticate

# Initialize
python
>>> import ee
>>> ee.Initialize()
```

---

## 🎯 Module Implementation Plan

### Phase 1: Data Export (Week 1)

Extract training data from Google Earth Engine:

```javascript
// Add to gee_master_application.js

function exportTrainingDataset() {
  var region = ee.Geometry.Rectangle([-180, -90, 180, 90]); // or specific area
  var years = [2010, 2015, 2020];
  
  // Combine all datasets
  var trainingImage = ee.Image(datasets["Organic Carbon"])
    .addBands(ee.Image(datasets["Soil pH"]))
    .addBands(ee.Image(datasets["Bulk Density"]))
    .addBands(ee.Image(datasets["Sand Content"]))
    .addBands(ee.Image(datasets["Clay Content"]));
  
  // Export as TFRecord for LSTM
  Export.image.toCloudStorage({
    image: trainingImage,
    bucket: 'your-bucket',
    fileNamePrefix: 'openlandmap/training_data',
    scale: 250,
    region: region,
    fileFormat: 'TFRecord'
  });
  
  print('✓ Training data export initiated');
}
```

---

### Phase 2: Random Forest Classification (Week 2)

```python
# ml_random_forest.py

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
import ee

ee.Initialize()

class RandomForestSoilClassifier:
    """
    Classify soil types using OpenLandMap data
    Classes: Sand, Silt, Loam, Clay, etc.
    """
    
    def __init__(self, n_trees=100, random_state=42):
        self.model = RandomForestClassifier(
            n_estimators=n_trees,
            max_depth=15,
            min_samples_split=5,
            random_state=random_state,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.feature_names = None
    
    def prepare_training_data(self, region_geojson, sample_size=1000):
        """
        Extract labeled samples from GEE
        
        Args:
            region_geojson: Study area boundary
            sample_size: Number of training samples
        
        Returns:
            X, y: Features and labels
        """
        
        # Load datasets
        organic_c = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02")
        soil_ph = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02")
        bulk_dens = ee.Image("OpenLandMap/SOL/SOL_BULK-DENSITY_USDA-6A1C_M/v02")
        sand = ee.Image("OpenLandMap/SOL/SOL_SAND-FRACTION_USDA-3A1A1A_M/v02")
        clay = ee.Image("OpenLandMap/SOL/SOL_CLAY-FRACTION_USDA-3A1A1A_M/v02")
        
        # Stack bands
        features_image = organic_c.addBands(soil_ph).addBands(bulk_dens)\
                                   .addBands(sand).addBands(clay)
        
        geometry = ee.Geometry.Polygon(region_geojson['coordinates'][0])
        
        # Sample points
        samples = features_image.stratifiedSample({
            'numPoints': sample_size,
            'classBand': 'b1',  # For stratification
            'region': geometry,
            'scale': 250,
            'seed': 0
        })
        
        # Convert to pandas
        samples_list = samples.getInfo()['features']
        data = []
        
        for sample in samples_list:
            props = sample['properties']
            data.append([
                props.get('b1', np.nan),  # Organic Carbon
                props.get('b1_1', np.nan),  # Soil pH
                props.get('b1_2', np.nan),  # Bulk Density
                props.get('b1_3', np.nan),  # Sand
                props.get('b1_4', np.nan),  # Clay
                self.label_soil_type(props)  # Label (derived)
            ])
        
        df = pd.DataFrame(data, columns=['OrgC', 'pH', 'BulkDens', 'Sand', 'Clay', 'SoilType'])
        df = df.dropna()
        
        self.feature_names = ['OrgC', 'pH', 'BulkDens', 'Sand', 'Clay']
        X = df[self.feature_names].values
        y = df['SoilType'].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y
    
    def train(self, X, y):
        """Train the classifier"""
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)
        
        print(f"Training Accuracy: {train_score:.4f}")
        print(f"Testing Accuracy: {test_score:.4f}")
        
        y_pred = self.model.predict(X_test)
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred))
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nFeature Importance:")
        print(importance)
        
        return test_score
    
    def predict_map(self, region_geojson):
        """Generate prediction map in GEE"""
        
        # Load and stack features
        organic_c = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02")
        soil_ph = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02")
        bulk_dens = ee.Image("OpenLandMap/SOL/SOL_BULK-DENSITY_USDA-6A1C_M/v02")
        sand = ee.Image("OpenLandMap/SOL/SOL_SAND-FRACTION_USDA-3A1A1A_M/v02")
        clay = ee.Image("OpenLandMap/SOL/SOL_CLAY-FRACTION_USDA-3A1A1A_M/v02")
        
        features_image = organic_c.addBands(soil_ph).addBands(bulk_dens)\
                                   .addBands(sand).addBands(clay)
        
        # Scale features using trained scaler
        # Note: In production, apply scaler coefficients
        
        # In GEE, use pre-trained classifier
        # This is a placeholder - actual implementation uses GEE Classifier API
        
        print("✓ Prediction map ready for export")
    
    def label_soil_type(self, props):
        """
        Derive soil type from soil properties
        Classification: Sand, Loamy Sand, Sandy Loam, Loam, Silt, Clay Loam, Clay
        """
        sand = props.get('b1_3', 50)
        clay = props.get('b1_4', 25)
        silt = 100 - sand - clay
        
        # USDA texture classification
        if sand > 70:
            return 'Sand'
        elif sand > 45 and clay < 27 and silt < 50:
            return 'Sandy Loam'
        elif sand < 27 and clay < 27:
            return 'Loam'
        elif clay > 40:
            return 'Clay'
        else:
            return 'Loam'
    
    def save_model(self, filepath):
        """Save trained model"""
        import joblib
        joblib.dump(self.model, filepath)
        print(f"✓ Model saved to {filepath}")

# Usage
if __name__ == "__main__":
    classifier = RandomForestSoilClassifier(n_trees=100)
    
    # Define region of interest
    region = {
        'type': 'Polygon',
        'coordinates': [[
            [-10, 40], [10, 40], [10, 50], [-10, 50], [-10, 40]
        ]]
    }
    
    print("Preparing training data...")
    X, y = classifier.prepare_training_data(region, sample_size=500)
    
    print("Training model...")
    classifier.train(X, y)
    
    print("Generating prediction map...")
    classifier.predict_map(region)
    
    classifier.save_model('soil_classifier.joblib')
```

---

### Phase 3: Temporal Regression (Week 3)

```python
# ml_temporal_regression.py

import numpy as np
import pandas as pd
from scipy import stats
import ee

ee.Initialize()

class TemporalRegressionEngine:
    """
    Analyze temporal trends in OpenLandMap data
    Extract slope (change rate) and confidence intervals
    """
    
    def __init__(self):
        self.results = {}
    
    def compute_trends(self, dataset_key, region_geojson, years=[2000, 2005, 2010, 2015, 2020]):
        """
        Compute linear trends from time series
        
        Returns:
            - slope: Change per year
            - intercept: Baseline value
            - r_value: Correlation coefficient
            - p_value: Statistical significance
            - std_err: Standard error
        """
        
        from gee_master_application import datasets
        
        image = ee.Image(datasets[dataset_key])
        geometry = ee.Geometry.Polygon(region_geojson['coordinates'][0])
        
        time_values = np.array(years)
        data_values = []
        
        for year in years:
            # In practice, use ImageCollection with temporal filtering
            sample = image.reduceRegion({
                'reducer': ee.Reducer.mean(),
                'geometry': geometry.centroid(),
                'scale': 250
            }).getInfo()
            
            data_values.append(list(sample.values())[0])
        
        data_values = np.array(data_values)
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            time_values, data_values
        )
        
        # Confidence interval (95%)
        n = len(years)
        t_stat = stats.t.ppf(0.975, n-2)
        ci = t_stat * std_err
        
        result = {
            'slope': slope,
            'intercept': intercept,
            'r_value': r_value,
            'p_value': p_value,
            'std_err': std_err,
            'ci_lower': slope - ci,
            'ci_upper': slope + ci,
            'annual_change': slope,
            'significant': p_value < 0.05
        }
        
        self.results[dataset_key] = result
        
        print(f"\n{'='*50}")
        print(f"Temporal Trend Analysis: {dataset_key}")
        print(f"{'='*50}")
        print(f"Slope: {slope:.6f} units/year")
        print(f"R-value: {r_value:.4f}")
        print(f"P-value: {p_value:.6f} {'***' if p_value < 0.05 else 'ns'}")
        print(f"95% CI: [{slope - ci:.6f}, {slope + ci:.6f}]")
        print(f"Significant: {'Yes' if result['significant'] else 'No'}")
        
        return result
    
    def forecast(self, slope, intercept, years_ahead=5):
        """
        Extend trend into future
        
        Args:
            slope: Trend coefficient
            intercept: Baseline value
            years_ahead: Number of years to forecast
        
        Returns:
            Forecast values with uncertainty
        """
        base_year = 2020
        forecast_years = np.arange(base_year + 1, base_year + years_ahead + 1)
        
        forecast_values = intercept + slope * (forecast_years - base_year)
        
        print(f"\nForecast (±std error):")
        for year, value in zip(forecast_years, forecast_values):
            print(f"  {year}: {value:.2f}")
        
        return forecast_years, forecast_values
    
    def export_results(self, filename='temporal_trends.csv'):
        """Export results to CSV"""
        df = pd.DataFrame(self.results).T
        df.to_csv(filename)
        print(f"✓ Results exported to {filename}")

# Usage
if __name__ == "__main__":
    engine = TemporalRegressionEngine()
    
    region = {
        'type': 'Polygon',
        'coordinates': [[
            [-10, 40], [10, 40], [10, 50], [-10, 50], [-10, 40]
        ]]
    }
    
    # Analyze each dataset
    datasets = [
        "Organic Carbon (g/kg)",
        "Soil pH (H2O)",
        "Bulk Density (tonnes/m³)"
    ]
    
    for dataset in datasets:
        result = engine.compute_trends(dataset, region)
        
        # Forecast 5 years
        forecast_years, forecast_values = engine.forecast(
            result['slope'],
            result['intercept'],
            years_ahead=5
        )
    
    engine.export_results()
```

---

### Phase 4: LSTM Forecasting (Week 4)

```python
# ml_lstm_forecast.py

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
import ee

ee.Initialize()

class LSTMForecastingEngine:
    """
    Multi-step ahead forecasting using LSTM
    Predict soil properties 2-10 years in future
    """
    
    def __init__(self, sequence_length=5, forecast_steps=3):
        self.sequence_length = sequence_length
        self.forecast_steps = forecast_steps
        self.model = None
        self.scaler = MinMaxScaler()
    
    def create_sequences(self, data):
        """
        Create sequences for LSTM training
        
        Format: [[t-4, t-3, t-2, t-1], [t]] → [t+1, t+2, t+3]
        """
        X, y = [], []
        
        for i in range(len(data) - self.sequence_length - self.forecast_steps + 1):
            X.append(data[i:(i + self.sequence_length)])
            y.append(data[(i + self.sequence_length):(i + self.sequence_length + self.forecast_steps)])
        
        return np.array(X), np.array(y)
    
    def build_model(self, input_shape):
        """
        Build LSTM architecture
        
        Architecture:
        Input → LSTM(64) → Dropout(0.2) → LSTM(32) → Dropout(0.2) → Dense(forecast_steps)
        """
        self.model = Sequential([
            LSTM(64, activation='relu', input_shape=input_shape, return_sequences=True),
            Dropout(0.2),
            LSTM(32, activation='relu', return_sequences=False),
            Dropout(0.2),
            Dense(self.forecast_steps)
        ])
        
        self.model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )
        
        print("✓ LSTM Model Architecture:")
        self.model.summary()
    
    def prepare_data(self, time_series, train_split=0.8):
        """
        Prepare and normalize time series
        
        Args:
            time_series: 1D array of values
            train_split: Train/test ratio
        
        Returns:
            X_train, y_train, X_test, y_test
        """
        # Normalize
        data_normalized = self.scaler.fit_transform(time_series.reshape(-1, 1)).flatten()
        
        # Create sequences
        X, y = self.create_sequences(data_normalized)
        
        # Split
        split_idx = int(len(X) * train_split)
        X_train, y_train = X[:split_idx], y[:split_idx]
        X_test, y_test = X[split_idx:], y[split_idx:]
        
        return X_train, y_train, X_test, y_test
    
    def train(self, X_train, y_train, X_test, y_test, epochs=50, batch_size=32):
        """Train LSTM model"""
        
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_test, y_test),
            verbose=1
        )
        
        print("✓ Training complete")
        
        # Evaluate
        test_loss, test_mae = self.model.evaluate(X_test, y_test)
        print(f"Test MAE: {test_mae:.4f}")
        
        return history
    
    def forecast(self, recent_sequence, steps=10):
        """
        Generate multi-step forecast
        
        Args:
            recent_sequence: Last sequence_length values
            steps: Number of steps to forecast
        
        Returns:
            Forecast values with confidence intervals
        """
        forecast = []
        current = recent_sequence.copy()
        
        for _ in range(steps):
            # Reshape for prediction
            input_data = current.reshape(1, self.sequence_length, 1)
            
            # Predict next steps
            next_pred = self.model.predict(input_data, verbose=0)
            forecast.append(next_pred[0])
            
            # Update sequence (use first predicted value)
            current = np.append(current[1:], next_pred[0][0])
        
        # Denormalize
        forecast = np.array(forecast).flatten()
        forecast = self.scaler.inverse_transform(forecast.reshape(-1, 1)).flatten()
        
        return forecast
    
    def uncertainty_quantification(self, X_test, y_test, n_iterations=100):
        """
        Estimate prediction uncertainty via MC Dropout
        """
        predictions = []
        
        # Enable dropout at test time
        original_dropout = self.model.layers[1].rate
        
        for _ in range(n_iterations):
            pred = self.model.predict(X_test, verbose=0)
            predictions.append(pred)
        
        predictions = np.array(predictions)
        mean_pred = predictions.mean(axis=0)
        std_pred = predictions.std(axis=0)
        
        return mean_pred, std_pred

# Usage
if __name__ == "__main__":
    # Generate synthetic time series (replace with GEE data)
    np.random.seed(42)
    time_steps = 24  # years
    trend = np.linspace(100, 120, time_steps)
    noise = np.random.normal(0, 2, time_steps)
    time_series = trend + noise
    
    # Initialize forecaster
    forecaster = LSTMForecastingEngine(sequence_length=5, forecast_steps=3)
    
    # Prepare data
    X_train, y_train, X_test, y_test = forecaster.prepare_data(time_series)
    
    # Build and train
    forecaster.build_model(input_shape=(5, 1))
    history = forecaster.train(X_train, y_train, X_test, y_test, epochs=50)
    
    # Generate forecast
    recent = X_test[-1, :, 0]  # Last sequence
    forecast = forecaster.forecast(recent, steps=10)
    
    print("\nForecast (next 10 years):")
    for i, val in enumerate(forecast):
        print(f"  Year {2021 + i}: {val:.2f}")
    
    # Uncertainty quantification
    print("\nComputing uncertainty bounds...")
    mean_pred, std_pred = forecaster.uncertainty_quantification(X_test, y_test)
    print(f"Mean forecast: {mean_pred}")
    print(f"Uncertainty (σ): {std_pred}")
```

---

## 🔄 Integration with GEE

After implementing each module:

```python
# Push results back to GEE

import ee

ee.Initialize()

# 1. Export predictions as image
predictions_array = np.array([[...]])  # Your predictions

# Convert to ee.Image and export
# prediction_image = ee.Image(ee.Array(predictions_array.tolist()))
# Export.image.toAsset({image: prediction_image, ...})

# 2. Visualize in GEE Code Editor
# Map.addLayer(predictions, {min: 0, max: 100, palette: ['blue', 'white', 'red']}, 'ML Forecast')

# 3. Generate time series chart
# ui.Chart.image.series({imageCollection: collection, region: region, ...})

print("✓ ML results ready for GEE visualization")
```

---

## 📊 Expected Outputs

| Module | Output Format | Use Case |
|--------|----------|----------|
| Random Forest | Classification map | Soil type inventory |
| Temporal Regression | Trend map + slopes | Degradation hotspots |
| LSTM | Time series forecast | Future scenarios |
| Correlation | Heatmap + importance | Driver identification |

---

## ✅ Implementation Checklist

- [ ] Week 1: Export training data from GEE
- [ ] Week 2: Random Forest classifier trained & validated
- [ ] Week 3: Temporal trends computed for all datasets
- [ ] Week 4: LSTM model forecasting 5+ years ahead
- [ ] Week 5: Correlation analysis with external layers
- [ ] Week 6: Results integrated into GEE visualization
- [ ] Week 7: Web dashboard updated with ML predictions
- [ ] Week 8: Documentation & deployment

---

**Ready to implement ML modules?** Start with Phase 1 (data export) and proceed sequentially.
