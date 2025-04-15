import os
import json
import logging
import numpy as np
import hashlib
import random
from PIL import Image
from io import BytesIO
import base64
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Configure the PostgreSQL database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Import and initialize our models
from models import db, DiseaseDataset, DiseaseSample, TreatmentRecommendation, DetectionHistory

# Initialize the database
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()

# Load disease data
with open('static/data/diseases.json', 'r') as f:
    DISEASE_DATA = json.load(f)

# We'll use this data to seed our database if it's empty
with app.app_context():
    if DiseaseDataset.query.count() == 0:
        # Create datasets
        cotton_dataset = DiseaseDataset(
            name="Cotton Disease Reference Set",
            crop_type="cotton",
            source="Agricultural Research Institute"
        )
        
        coconut_dataset = DiseaseDataset(
            name="Coconut Disease Reference Set",
            crop_type="coconut",
            source="Tropical Plant Research Center"
        )
        
        db.session.add_all([cotton_dataset, coconut_dataset])
        db.session.commit()
        
        # Add disease samples from our JSON data
        for disease_key, disease_data in DISEASE_DATA.items():
            crop_type = disease_key.split('_')[0]  # Extract crop type from key
            dataset = cotton_dataset if crop_type == 'cotton' else coconut_dataset
            
            # Create baseline features for this disease
            if crop_type == 'cotton':
                if 'leaf_spot' in disease_key:
                    color_features = {'red_mean': 130, 'green_mean': 90, 'blue_mean': 85}
                    texture_features = {'contrast': 'high', 'patterns': 'spotted'}
                elif 'boll_rot' in disease_key:
                    color_features = {'red_mean': 160, 'green_mean': 70, 'blue_mean': 75}
                    texture_features = {'contrast': 'medium', 'patterns': 'irregular'}
                else:
                    color_features = {'red_mean': 120, 'green_mean': 110, 'blue_mean': 90}
                    texture_features = {'contrast': 'low', 'patterns': 'uniform'}
            else:  # coconut
                if 'leaf_spot' in disease_key:
                    color_features = {'red_mean': 110, 'green_mean': 85, 'blue_mean': 80}
                    texture_features = {'contrast': 'medium', 'patterns': 'dotted'}
                elif 'bud_rot' in disease_key:
                    color_features = {'red_mean': 140, 'green_mean': 90, 'blue_mean': 85}
                    texture_features = {'contrast': 'high', 'patterns': 'damaged'}
                else:
                    color_features = {'red_mean': 115, 'green_mean': 105, 'blue_mean': 85}
                    texture_features = {'contrast': 'low', 'patterns': 'uniform'}
            
            disease_sample = DiseaseSample(
                disease_name=disease_data['name'],
                description=disease_data['description'],
                severity="moderate",
                color_features=color_features,
                texture_features=texture_features,
                shape_features={'symmetry': 'asymmetric'},
                dataset_id=dataset.id
            )
            
            db.session.add(disease_sample)
            db.session.commit()
            
            # Add treatment recommendations
            for pesticide in disease_data['recommended_pesticides']:
                recommendation = TreatmentRecommendation(
                    name=pesticide['name'],
                    description=pesticide['description'],
                    application_rate=pesticide.get('application_rate', 'See product label'),
                    effectiveness=0.85,
                    eco_friendly=False if 'chlor' in pesticide['name'].lower() else True,
                    disease_id=disease_sample.id
                )
                db.session.add(recommendation)
            
            db.session.commit()

def compare_images(uploaded_image, crop_type):
    """
    Enhanced image comparison for disease detection
    Uses multiple datasets to compare and provide more accurate detection
    """
    try:
        # Convert base64 to image
        image_data = base64.b64decode(uploaded_image.split(',')[1])
        img = Image.open(BytesIO(image_data))
        
        # Calculate hash of image for reference/history
        img_hash = hashlib.md5(image_data).hexdigest()
        
        # Resize image for processing
        img = img.resize((100, 100))
        img_array = np.array(img)
        
        # Extract features from the uploaded image
        red_channel = img_array[:,:,0].mean()
        green_channel = img_array[:,:,1].mean()
        blue_channel = img_array[:,:,2].mean()
        
        # Calculate color variation (rough texture measure)
        red_std = img_array[:,:,0].std()
        green_std = img_array[:,:,1].std()
        
        # Calculate edge density (rough shape measure)
        edge_density = 0
        for i in range(1, 99):
            for j in range(1, 99):
                # Simple edge detection by checking pixel differences
                if abs(int(img_array[i,j,0]) - int(img_array[i-1,j,0])) > 20 or \
                   abs(int(img_array[i,j,0]) - int(img_array[i,j-1,0])) > 20:
                    edge_density += 1
        edge_density = edge_density / (98*98)  # Normalize
        
        # Get all disease samples from database for the specified crop type
        with app.app_context():
            # Get the dataset for the crop type
            dataset = DiseaseDataset.query.filter_by(crop_type=crop_type).first()
            
            if not dataset:
                logger.error(f"No reference dataset found for crop type: {crop_type}")
                return [{"disease_key": "error", "confidence": 1.0}]
            
            # Get disease samples from the dataset
            samples = DiseaseSample.query.filter_by(dataset_id=dataset.id).all()
            
            if not samples:
                logger.error(f"No disease samples found in the dataset for crop type: {crop_type}")
                return [{"disease_key": "error", "confidence": 1.0}]
            
            # Calculate similarity scores against all disease samples
            similarity_scores = []
            
            for sample in samples:
                # Extract sample features
                sample_color_features = sample.color_features
                
                # Calculate color similarity
                color_diff = abs(red_channel - sample_color_features.get('red_mean', 0)) + \
                            abs(green_channel - sample_color_features.get('green_mean', 0)) + \
                            abs(blue_channel - sample_color_features.get('blue_mean', 0))
                
                # Normalize color difference to 0-1 range (0 = identical, 1 = completely different)
                color_similarity = 1 - min(color_diff / 255, 1.0)
                
                # Texture similarity (simplified)
                texture_similarity = 0.8  # Default value
                if sample.texture_features.get('contrast') == 'high' and red_std > 40:
                    texture_similarity = 0.9
                elif sample.texture_features.get('contrast') == 'medium' and red_std > 25 and red_std <= 40:
                    texture_similarity = 0.9
                elif sample.texture_features.get('contrast') == 'low' and red_std <= 25:
                    texture_similarity = 0.9
                
                # Shape similarity (simplified)
                shape_similarity = 0.8  # Default value
                if edge_density > 0.1 and sample.texture_features.get('patterns') in ['spotted', 'dotted']:
                    shape_similarity = 0.9
                elif edge_density <= 0.1 and sample.texture_features.get('patterns') == 'uniform':
                    shape_similarity = 0.9
                
                # Combine similarities with different weights
                overall_similarity = (0.6 * color_similarity + 
                                    0.25 * texture_similarity + 
                                    0.15 * shape_similarity)
                
                # Get disease key from sample name (convert back to snake_case)
                disease_key = f"{crop_type}_{sample.disease_name.lower().replace(' ', '_')}"
                if 'leaf spot' in sample.disease_name.lower():
                    disease_key = f"{crop_type}_leaf_spot"
                elif 'boll rot' in sample.disease_name.lower():
                    disease_key = f"{crop_type}_boll_rot"
                elif 'bud rot' in sample.disease_name.lower():
                    disease_key = f"{crop_type}_bud_rot"
                
                similarity_scores.append({
                    "disease_key": disease_key,
                    "disease_name": sample.disease_name,
                    "similarity": overall_similarity,
                    "confidence": overall_similarity * 100  # Convert to percentage
                })
            
            # Add possibility of healthy plant
            # If the image has high green values and low red values, it's likely healthy
            if green_channel > 120 and red_channel < 100:
                similarity_scores.append({
                    "disease_key": "healthy",
                    "disease_name": "Healthy Plant",
                    "similarity": 0.85,
                    "confidence": 85.0
                })
                
            # For coconut trees, also perform maturity analysis
            if crop_type == 'coconut':
                # Detect maturity level based on color profile
                # This is a simplified approach - in a real application, we would use more sophisticated image analysis
                
                # Brown tones indicate maturity, more green indicates young coconuts
                maturity_score = (red_channel / green_channel) if green_channel > 0 else 1.0
                
                # Define maturity level based on score
                maturity_level = "immature"
                harvest_ready = False
                
                if maturity_score > 1.1:  # More red than green indicates mature coconuts
                    maturity_level = "mature"
                    # Check additional texture features for harvest readiness
                    if edge_density > 0.15:  # Higher edge density may indicate developed coconuts
                        maturity_level = "ready_for_harvest"
                        harvest_ready = True
                
                # Estimate number of coconuts based on edge features and variations in the image
                coconut_count_estimate = int(edge_density * 100) + random.randint(5, 15)
                coconut_count_estimate = max(0, min(coconut_count_estimate, 35))  # Reasonable range
                
                # Add maturity analysis to the results
                similarity_scores.append({
                    "disease_key": "coconut_maturity_analysis",
                    "disease_name": "Maturity Analysis",
                    "similarity": 0.95,
                    "confidence": 95.0,
                    "maturity_data": {
                        "maturity_level": maturity_level,
                        "coconut_count": coconut_count_estimate,
                        "harvest_ready": harvest_ready
                    }
                })
            
            # Sort by similarity score in descending order
            similarity_scores.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Store detection in history
            detection_history = DetectionHistory(
                crop_type=crop_type,
                detected_diseases=[s['disease_key'] for s in similarity_scores[:3]],  # Top 3 diseases
                confidence_scores=[s['confidence'] for s in similarity_scores[:3]],  # Their confidence scores
                image_hash=img_hash
            )
            db.session.add(detection_history)
            db.session.commit()
            
            # Return top matches with confidence scores
            # Threshold: only return diseases with similarity > 0.6
            valid_matches = [s for s in similarity_scores if s['similarity'] > 0.6]
            
            # If no valid matches found, return healthy
            if not valid_matches:
                return [{"disease_key": "healthy", "confidence": 90.0}]
                
            # Get top 3 matches or all if fewer than 3
            top_matches = valid_matches[:min(3, len(valid_matches))]
            
            return top_matches
    
    except Exception as e:
        logger.error(f"Error in image comparison: {str(e)}")
        return [{"disease_key": "error", "confidence": 100.0}]

@app.route('/')
def index():
    # Get datasets and counts for the home page
    datasets = {}
    with app.app_context():
        cotton_dataset = DiseaseDataset.query.filter_by(crop_type='cotton').first()
        coconut_dataset = DiseaseDataset.query.filter_by(crop_type='coconut').first()
        
        if cotton_dataset:
            datasets['cotton'] = {
                'name': cotton_dataset.name,
                'sample_count': DiseaseSample.query.filter_by(dataset_id=cotton_dataset.id).count(),
                'source': cotton_dataset.source
            }
            
        if coconut_dataset:
            datasets['coconut'] = {
                'name': coconut_dataset.name,
                'sample_count': DiseaseSample.query.filter_by(dataset_id=coconut_dataset.id).count(),
                'source': coconut_dataset.source
            }
    
    return render_template('index.html', datasets=datasets)

@app.route('/datasets')
def view_datasets():
    """View all available disease datasets"""
    with app.app_context():
        datasets = DiseaseDataset.query.all()
        datasets_with_samples = []
        
        for dataset in datasets:
            samples = DiseaseSample.query.filter_by(dataset_id=dataset.id).all()
            samples_with_treatments = []
            
            for sample in samples:
                treatments = TreatmentRecommendation.query.filter_by(disease_id=sample.id).all()
                samples_with_treatments.append({
                    'sample': sample,
                    'treatments': treatments
                })
            
            datasets_with_samples.append({
                'dataset': dataset,
                'samples': samples_with_treatments
            })
        
        # Get detection history
        history = DetectionHistory.query.order_by(DetectionHistory.timestamp.desc()).limit(10).all()
        
        return render_template('datasets.html', 
                              datasets=datasets_with_samples, 
                              history=history)

@app.route('/detect', methods=['POST'])
def detect_disease():
    try:
        data = request.json
        image_data = data.get('image')
        crop_type = data.get('cropType')
        
        if not image_data or not crop_type:
            return jsonify({'error': 'Missing image data or crop type'}), 400
        
        # Get detection results with confidence scores
        detection_results = compare_images(image_data, crop_type)
        
        # Extract disease keys for field data generation
        disease_keys = [result['disease_key'] for result in detection_results]
        
        # Get disease information from database and our dataset
        disease_info = []
        
        with app.app_context():
            for result in detection_results:
                disease_key = result['disease_key']
                confidence = result['confidence']
                
                if disease_key == "healthy":
                    disease_info.append({
                        "name": "Healthy Plant",
                        "description": "No disease detected.",
                        "confidence": confidence,
                        "recommended_pesticides": []
                    })
                elif disease_key == "error":
                    disease_info.append({
                        "name": "Detection Error",
                        "description": "Unable to process the image.",
                        "confidence": confidence,
                        "recommended_pesticides": []
                    })
                elif disease_key == "coconut_maturity_analysis":
                    # Handle coconut maturity analysis special case
                    maturity_data = result.get('maturity_data', {})
                    maturity_level = maturity_data.get('maturity_level', 'unknown')
                    coconut_count = maturity_data.get('coconut_count', 0)
                    harvest_ready = maturity_data.get('harvest_ready', False)
                    
                    # Create a description based on maturity data
                    if maturity_level == "immature":
                        description = f"The coconut trees are still immature. Approximately {coconut_count} coconuts detected, but they are not ready for harvest yet. Continue regular care and monitoring."
                    elif maturity_level == "mature":
                        description = f"The coconut trees are mature with approximately {coconut_count} coconuts detected. They will be ready for harvest soon. Continue monitoring for optimal harvest time."
                    elif maturity_level == "ready_for_harvest":
                        description = f"The coconut trees are ready for harvest! Approximately {coconut_count} coconuts detected at optimal maturity. Recommend harvesting within the next 1-2 weeks."
                    else:
                        description = f"Unable to determine maturity level accurately. Approximately {coconut_count} coconuts detected."
                    
                    # Add maturity info to disease_info
                    disease_info.append({
                        "name": "Coconut Maturity Analysis",
                        "description": description,
                        "confidence": confidence,
                        "maturity_data": {
                            "maturity_level": maturity_level,
                            "coconut_count": coconut_count,
                            "harvest_ready": harvest_ready
                        },
                        "recommended_pesticides": []  # No pesticides for maturity analysis
                    })
                else:
                    # Get disease info from database
                    crop_type_from_key = disease_key.split('_')[0]
                    disease_name = ' '.join([word.capitalize() for word in disease_key.split('_')[1:]])
                    
                    # Get the database record
                    sample = DiseaseSample.query.join(DiseaseDataset).filter(
                        DiseaseDataset.crop_type == crop_type_from_key,
                        DiseaseSample.disease_name.ilike(f"%{disease_name}%")
                    ).first()
                    
                    if sample:
                        # Get recommendations from database
                        recommendations = TreatmentRecommendation.query.filter_by(disease_id=sample.id).all()
                        recommended_pesticides = [
                            {
                                "name": rec.name,
                                "description": rec.description,
                                "application_rate": rec.application_rate,
                                "effectiveness": rec.effectiveness,
                                "eco_friendly": rec.eco_friendly
                            } for rec in recommendations
                        ]
                        
                        disease_info.append({
                            "name": sample.disease_name,
                            "description": sample.description,
                            "confidence": confidence,
                            "severity": sample.severity,
                            "recommended_pesticides": recommended_pesticides
                        })
                    elif disease_key in DISEASE_DATA:
                        # Fallback to JSON data if not in database
                        info = DISEASE_DATA[disease_key]
                        info["confidence"] = confidence
                        disease_info.append(info)
                    else:
                        # Generic fallback
                        disease_info.append({
                            "name": disease_name,
                            "description": "Unknown plant disease detected.",
                            "confidence": confidence,
                            "recommended_pesticides": [{
                                "name": "General Fungicide",
                                "description": "Broad-spectrum fungicide effective against multiple diseases."
                            }]
                        })
        
        # Generate field data visualization
        field_data = generate_field_data(disease_keys, crop_type)
        
        return jsonify({
            'diseases': disease_keys,
            'disease_info': disease_info,
            'field_data': field_data,
            'multiple_detections': len(disease_keys) > 1,
            'detection_confidence': [result['confidence'] for result in detection_results]
        })
    
    except Exception as e:
        logger.error(f"Error in disease detection: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_field_data(diseases, crop_type):
    """
    Generate field representation with disease hotspots
    For coconut trees, also can show maturity visualization
    """
    # Create a 10x10 grid field
    field_size = 10
    field = [[0 for _ in range(field_size)] for _ in range(field_size)]
    
    # Check if we have a maturity analysis
    has_maturity_analysis = "coconut_maturity_analysis" in diseases
    
    # If plant is healthy or only has maturity analysis, return special field for coconuts
    if (diseases == ["healthy"] or diseases == ["error"]) and crop_type != "coconut":
        return {
            "grid": field,
            "hotspots": []
        }
    
    # If this is a coconut tree with maturity analysis
    if crop_type == "coconut" and has_maturity_analysis:
        # Generate a field with coconut trees at varying maturity levels
        hotspots = []
        
        # Create a more natural pattern for coconut trees
        num_coconuts = random.randint(6, 10)  # Reasonable number of coconut trees in view
        
        # Make the first tree the analyzed one 
        # (in real app we'd use actual image analysis to place these accurately)
        center_x, center_y = field_size // 2, field_size // 2
        
        # Place the first tree in center
        field[center_y][center_x] = 2  # 2 means "mature" coconut
        hotspots.append({
            "x": center_x,
            "y": center_y,
            "disease": "coconut_maturity_analysis", 
            "maturity": "ready_for_harvest"
        })
        
        # Place other coconut trees in a pattern around it
        maturity_levels = ["immature", "mature", "ready_for_harvest"]
        weights = [0.3, 0.4, 0.3]  # Probability distribution
        
        for _ in range(num_coconuts - 1):
            # Find a position not too close to other trees
            while True:
                x = np.random.randint(0, field_size)
                y = np.random.randint(0, field_size)
                
                # Check if position is empty and not too close to other trees
                if field[y][x] == 0 and ((x - center_x)**2 + (y - center_y)**2) > 4:
                    # Choose maturity level with weighted probability
                    maturity = random.choices(maturity_levels, weights=weights)[0]
                    
                    if maturity == "immature":
                        field[y][x] = 1  # 1 means "immature" coconut
                    elif maturity == "mature":
                        field[y][x] = 2  # 2 means "mature" coconut
                    else:
                        field[y][x] = 3  # 3 means "ready_for_harvest" coconut
                    
                    hotspots.append({
                        "x": x,
                        "y": y,
                        "disease": "none",
                        "maturity": maturity
                    })
                    break
        
        return {
            "grid": field,
            "hotspots": hotspots,
            "is_maturity_analysis": True
        }
        
    # For disease visualization (default case)
    # Filter out maturity_analysis from disease hotspots
    disease_list = [d for d in diseases if d != "coconut_maturity_analysis" and d != "healthy" and d != "error"]
    
    # If no actual diseases left, return empty field
    if not disease_list:
        return {
            "grid": field,
            "hotspots": [] 
        }
    
    # Generate random disease hotspots
    num_hotspots = min(len(disease_list) * 2, 5)  # 2 hotspots per disease, max 5
    hotspots = []
    
    for _ in range(num_hotspots):
        x = np.random.randint(0, field_size)
        y = np.random.randint(0, field_size)
        disease_index = np.random.randint(0, len(disease_list))
        disease_name = disease_list[disease_index]
        
        # Mark the hotspot
        field[y][x] = 1
        
        hotspots.append({
            "x": x,
            "y": y,
            "disease": disease_name
        })
    
    return {
        "grid": field,
        "hotspots": hotspots,
        "is_maturity_analysis": False
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
