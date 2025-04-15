from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class DiseaseDataset(db.Model):
    """Model for disease reference datasets"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    crop_type = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    disease_samples = db.relationship('DiseaseSample', backref='dataset', lazy=True)
    
    def __repr__(self):
        return f"<Dataset {self.name}>"

class DiseaseSample(db.Model):
    """Model for individual disease samples in the reference datasets"""
    id = db.Column(db.Integer, primary_key=True)
    disease_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20))  # mild, moderate, severe
    
    # Image features (stored as JSON strings)
    color_features = db.Column(db.JSON)  # RGB distributions, histograms, etc.
    texture_features = db.Column(db.JSON)  # Texture patterns
    shape_features = db.Column(db.JSON)  # Shape descriptors
    
    # Foreign keys
    dataset_id = db.Column(db.Integer, db.ForeignKey('disease_dataset.id'), nullable=False)
    
    # Relationships
    recommendations = db.relationship('TreatmentRecommendation', backref='disease', lazy=True)
    
    def __repr__(self):
        return f"<Sample {self.disease_name} (Severity: {self.severity})>"

class TreatmentRecommendation(db.Model):
    """Model for treatment recommendations for each disease"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    application_rate = db.Column(db.String(100))
    effectiveness = db.Column(db.Float)  # 0-1 rating
    eco_friendly = db.Column(db.Boolean, default=False)
    
    # Foreign key
    disease_id = db.Column(db.Integer, db.ForeignKey('disease_sample.id'), nullable=False)
    
    def __repr__(self):
        return f"<Treatment {self.name} for {self.disease.disease_name}>"

class DetectionHistory(db.Model):
    """Model for storing user detection history"""
    id = db.Column(db.Integer, primary_key=True)
    crop_type = db.Column(db.String(50), nullable=False)
    detected_diseases = db.Column(db.JSON)
    confidence_scores = db.Column(db.JSON)
    image_hash = db.Column(db.String(64))  # Store hash of image for reference
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Detection {self.id} on {self.timestamp}>"