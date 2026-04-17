from app import app, db
from models import FoodItem

with app.app_context():
    menu = [
        # TIFFINS
        {
            "name": "Crispy Masala Dosa", 
            "desc": "A golden, crispy South Indian crepe stuffed with a spiced potato mash, served with hot sambar and fresh coconut chutney.", 
            "price": 120.0,
            "img": "https://images.unsplash.com/photo-1589301760014-d929f39ce9b1?w=400&q=80"
        },
        {
            "name": "Steaming Idli Sambar", 
            "desc": "Three unbelievably soft steamed rice cakes perfect for dipping into our signature tangy lentil sambar.", 
            "price": 90.0,
            "img": "https://images.unsplash.com/photo-1626776876729-bab4369a5a5a?w=400&q=80"
        },
        {
            "name": "Classic Poori Bhaji", 
            "desc": "Fluffy, balloon-like deep-fried Indian bread served alongside a mildly spiced, deeply aromatic tomato-potato curry.", 
            "price": 140.0,
            "img": "https://images.unsplash.com/photo-1606491956689-2ea866880c84?w=400&q=80"
        },
        
        # MEALS
        {
            "name": "South Indian Full Meals (Thali)", 
            "desc": "A traditional heavy platter featuring steamed rice, sambar, rasam, two vegetable curries, curd, crispy papad, and a sweet.", 
            "price": 250.0,
            "img": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80"
        },
        {
            "name": "North Indian Royal Thali", 
            "desc": "A premium platter featuring butter chicken, dal makhani, paneer tikka, jeera rice, two buttery parathas, and a hot gulab jamun.", 
            "price": 420.0,
            "img": "https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&q=80"
        },
        {
            "name": "Andhra Spicy Meals", 
            "desc": "Authentic, fiery Andhra meals served with traditional gun powder, copious ghee, gongura pickle, thick pappu, and rasam.", 
            "price": 280.0,
            "img": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80"
        },

        # BIRYANI VARIETIES 
        {
            "name": "Hyderabadi Dum Chicken Biryani", 
            "desc": "Our world-famous, incredibly flavorful basmati rice layered overnight with marinated chicken and cooked gently on dum.", 
            "price": 400.0,
            "img": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&q=80"
        },
        {
            "name": "Signature Mutton Biryani", 
            "desc": "Prime cuts of melt-in-your-mouth mutton slow-cooked with highly fragrant whole spices and premium long-grain basmati rice.", 
            "price": 550.0,
            "img": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=400&q=80"
        },
        {
            "name": "Smoked Paneer Tikka Biryani", 
            "desc": "A 100% vegetarian masterpiece combining smoky, charred tandoori paneer tikka nested entirely in spiced saffron rice.", 
            "price": 320.0,
            "img": "https://images.unsplash.com/photo-1631452180519-c014fe946bc0?w=400&q=80"
        }
    ]
    
    for item in menu:
        if not FoodItem.query.filter_by(name=item['name']).first():
            f = FoodItem(
                name=item['name'], 
                description=item['desc'], 
                price=item['price'],
                image_url=item['img']
            )
            db.session.add(f)
            
    db.session.commit()
    print("New Indian Menu Items (Tiffins, Meals, Biryani) populated!")
