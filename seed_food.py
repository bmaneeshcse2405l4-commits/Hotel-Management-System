from app import app, db
from models import FoodItem

with app.app_context():
    menu = [
        {
            "name": "Continental Breakfast", 
            "desc": "Eggs to order, toast, sausages, hash browns, and fresh juice.", 
            "price": 450.0,
            "img": "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?w=400&q=80"
        },
        {
            "name": "Royal Chicken Biryani", 
            "desc": "Aromatic basmati rice slowly cooked with marinated chicken and rich spices.", 
            "price": 550.0,
            "img": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&q=80"
        },
        {
            "name": "Paneer Butter Masala", 
            "desc": "Soft cottage cheese cubes simmered in a mildly spiced, rich tomato and butter gravy.", 
            "price": 380.0,
            "img": "https://images.unsplash.com/photo-1631452180519-c014fe946bc0?w=400&q=80"
        },
        {
            "name": "Dal Makhani & Naan", 
            "desc": "Signature slow-cooked black lentils served with two freshly baked garlic naans.", 
            "price": 320.0,
            "img": "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&q=80"
        },
        {
            "name": "Hyderabadi Mutton Curry", 
            "desc": "Tender mutton pieces cooked in regional aromatic spices and rich gravy.", 
            "price": 650.0,
            "img": "https://images.unsplash.com/photo-1603569283847-aa295f0d016a?w=400&q=80"
        },
        {
            "name": "Club Sandwich with Fries", 
            "desc": "A classic triple-decker sandwich loaded with chicken, egg, cheese, and fresh veggies.", 
            "price": 350.0,
            "img": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400&q=80"
        },
        {
            "name": "Masala Chai & Samosa", 
            "desc": "Authentic Indian spiced tea served alongside two piping hot, crispy potato samosas.", 
            "price": 150.0,
            "img": "https://images.unsplash.com/photo-1599305090598-fe179d501227?w=400&q=80"
        },
        {
            "name": "Chocolate Lava Cake", 
            "desc": "Warm chocolate pastry with a molten center, served with a scoop of vanilla bean ice cream.", 
            "price": 280.0,
            "img": "https://images.unsplash.com/photo-1624353365286-3f8d62daad51?w=400&q=80"
        }
    ]
    
    for item in menu:
        # Check if exists to avoid duplicates if script is run multiple times
        if not FoodItem.query.filter_by(name=item['name']).first():
            f = FoodItem(
                name=item['name'], 
                description=item['desc'], 
                price=item['price'],
                image_url=item['img']
            )
            db.session.add(f)
            
    db.session.commit()
    print("Premium Kitchen Menu successfully populated!")
