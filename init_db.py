import os
from app import app, db, Usuario

with app.app_context():
    print("Eliminando base de datos antigua si existe...")
    # Buscamos la ruta real configurada
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Base de datos antigua eliminada.")
        
    print("Creando nuevas tablas...")
    db.create_all()
    
    print("Insertando usuario administrador...")
    admin = Usuario(username='admin', password='123')
    db.session.add(admin)
    db.session.commit()
    print("¡Base de datos inicializada con éxito!")