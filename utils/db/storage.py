
import sqlite3 as lite

class DatabaseManager(object):

    def __init__(self, path):
        self.conn = lite.connect(path)
        self.conn.execute('pragma foreign_keys = on')
        self.conn.commit()
        self.cur = self.conn.cursor()

    def create_tables(self):
        self.query('CREATE TABLE IF NOT EXISTS products (idx text, title text, body text, photo blob, price int, tag text)')
        self.query('CREATE TABLE IF NOT EXISTS orders (cid int, usr_name text, usr_address text, products text, delivery_slot text)')
        self.query('CREATE TABLE IF NOT EXISTS cart (cid int, idx text, quantity int)')
        self.query('CREATE TABLE IF NOT EXISTS categories (idx text, title text)')
        self.query('CREATE TABLE IF NOT EXISTS wallet (cid int, balance real)')
        self.query('CREATE TABLE IF NOT EXISTS questions (cid int, question text)')
        self.query('CREATE TABLE IF NOT EXISTS price_history (id INTEGER PRIMARY KEY AUTOINCREMENT, product_idx text, old_price int, new_price int, percentage real, admin_id int, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        self.query('CREATE TABLE IF NOT EXISTS admin_categories (admin_id int, category_idx text, PRIMARY KEY (admin_id, category_idx))')

    def migrate_orders_table(self):
        try:
            self.query('ALTER TABLE orders ADD COLUMN delivery_slot text')
        except:
            pass

    def grant_admin_categories(self, admin_ids):
        categories = self.fetchall('SELECT idx FROM categories')
        for admin_id in admin_ids:
            for (cat_idx,) in categories:
                existing = self.fetchone('SELECT 1 FROM admin_categories WHERE admin_id = ? AND category_idx = ?',
                                         (admin_id, cat_idx))
                if not existing:
                    self.query('INSERT OR IGNORE INTO admin_categories VALUES (?, ?)', (admin_id, cat_idx))
        
    def query(self, arg, values=None):
        if values == None:
            self.cur.execute(arg)
        else:
            self.cur.execute(arg, values)
        self.conn.commit()

    def fetchone(self, arg, values=None):
        if values == None:
            self.cur.execute(arg)
        else:
            self.cur.execute(arg, values)
        return self.cur.fetchone()

    def fetchall(self, arg, values=None):
        if values == None:
            self.cur.execute(arg)
        else:
            self.cur.execute(arg, values)
        return self.cur.fetchall()

    def __del__(self):
        self.conn.close()


'''

products: idx text, title text, body text, photo blob, price int, tag text

orders: cid int, usr_name text, usr_address text, products text

cart: cid int, idx text, quantity int ==> product_idx

categories: idx text, title text

wallet: cid int, balance real

questions: cid int, question text

'''
