from app import app, db
from models import FoodItem

with app.app_context():
    items = {
        "Paneer Butter Masala": "/static/images/paneer_masala.png",
        "Smoked Paneer Tikka Biryani": "/static/images/paneer_biryani.png",
        "Paneer Tikka Biryani": "/static/images/paneer_biryani.png" # Legacy name map
    }
    
    for name, img_path in items.items():
        food = FoodItem.query.filter_by(name=name).first()
        if food:
            food.image_url = img_path
            
    db.session.commit()
    print("Vegetarian premium items updated with new imagery!")
