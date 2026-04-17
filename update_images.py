from app import app, db
from models import FoodItem

with app.app_context():
    items = {
        "Hyderabadi Dum Chicken Biryani": "/static/images/biryani.png",
        "Crispy Masala Dosa": "/static/images/masala_dosa.png",
        "North Indian Royal Thali": "/static/images/thali.png",
        "Chocolate Lava Cake": "/static/images/lava_cake.png",
        # For legacy names if they still exist:
        "Royal Chicken Biryani": "/static/images/biryani.png",
        "Masala Dosa": "/static/images/masala_dosa.png"
    }
    
    for name, img_path in items.items():
        food = FoodItem.query.filter_by(name=name).first()
        if food:
            food.image_url = img_path
    
    db.session.commit()
    print("Local images mapped in DB.")
