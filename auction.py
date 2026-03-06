from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ipl-auction-secret-key-2025')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///ipl_auction.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')


# ─────────────────────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    team_name     = db.Column(db.String(100))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Player(db.Model):
    __tablename__ = 'player'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    role          = db.Column(db.String(50),  nullable=False)
    team          = db.Column(db.String(80))
    nationality   = db.Column(db.String(50))
    age           = db.Column(db.Integer)
    base_price    = db.Column(db.Integer, nullable=False)
    current_price = db.Column(db.Integer, nullable=False)
    sold_to       = db.Column(db.String(100), default=None)
    is_sold       = db.Column(db.Boolean, default=False)
    matches       = db.Column(db.Integer, default=0)
    runs          = db.Column(db.Integer, default=0)
    wickets       = db.Column(db.Integer, default=0)
    strike_rate   = db.Column(db.Float,   default=0.0)
    batting_avg   = db.Column(db.Float,   default=0.0)
    economy       = db.Column(db.Float,   default=0.0)
    catches       = db.Column(db.Integer, default=0)
    fifties       = db.Column(db.Integer, default=0)
    hundreds      = db.Column(db.Integer, default=0)
    highest_score = db.Column(db.Integer, default=0)
    best_bowling  = db.Column(db.String(20), default='-')
    bids = db.relationship('Bid', backref='player', lazy=True, cascade="all, delete-orphan")


class Bid(db.Model):
    __tablename__ = 'bid'
    id          = db.Column(db.Integer, primary_key=True)
    player_id   = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    bidder_name = db.Column(db.String(100), nullable=False)
    amount      = db.Column(db.Integer, nullable=False)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA
# ─────────────────────────────────────────────────────────────────────────────

PLAYERS = [
    dict(name="Virat Kohli",       role="Batsman",     team="Royal Challengers Bengaluru",
         nationality="Indian", age=35, base_price=200, current_price=200,
         matches=16, runs=741,  wickets=0,  strike_rate=154.7, batting_avg=61.8,
         economy=0.0, catches=8,  fifties=5, hundreds=1, highest_score=113, best_bowling='-'),
    dict(name="Rohit Sharma",      role="Batsman",     team="Mumbai Indians",
         nationality="Indian", age=37, base_price=160, current_price=160,
         matches=14, runs=531,  wickets=0,  strike_rate=148.3, batting_avg=40.8,
         economy=0.0, catches=6,  fifties=4, hundreds=1, highest_score=105, best_bowling='-'),
    dict(name="Shubman Gill",      role="Batsman",     team="Gujarat Titans",
         nationality="Indian", age=24, base_price=120, current_price=120,
         matches=16, runs=890,  wickets=0,  strike_rate=157.4, batting_avg=62.3,
         economy=0.0, catches=7,  fifties=6, hundreds=2, highest_score=129, best_bowling='-'),
    dict(name="Yashasvi Jaiswal",  role="Batsman",     team="Rajasthan Royals",
         nationality="Indian", age=22, base_price=110, current_price=110,
         matches=14, runs=435,  wickets=0,  strike_rate=163.5, batting_avg=39.5,
         economy=0.0, catches=5,  fifties=3, hundreds=1, highest_score=124, best_bowling='-'),
    dict(name="Suryakumar Yadav",  role="Batsman",     team="Mumbai Indians",
         nationality="Indian", age=33, base_price=160, current_price=160,
         matches=16, runs=942,  wickets=0,  strike_rate=182.5, batting_avg=63.4,
         economy=0.0, catches=11, fifties=6, hundreds=2, highest_score=117, best_bowling='-'),
    dict(name="Rinku Singh",       role="Batsman",     team="Kolkata Knight Riders",
         nationality="Indian", age=26, base_price=55,  current_price=55,
         matches=14, runs=474,  wickets=0,  strike_rate=173.6, batting_avg=59.3,
         economy=0.0, catches=5,  fifties=3, hundreds=0, highest_score=74,  best_bowling='-'),
    dict(name="KL Rahul",          role="WK-Batsman",  team="Lucknow Super Giants",
         nationality="Indian", age=32, base_price=140, current_price=140,
         matches=14, runs=520,  wickets=0,  strike_rate=135.4, batting_avg=43.3,
         economy=0.0, catches=22, fifties=4, hundreds=0, highest_score=82,  best_bowling='-'),
    dict(name="Rishabh Pant",      role="WK-Batsman",  team="Delhi Capitals",
         nationality="Indian", age=26, base_price=160, current_price=160,
         matches=16, runs=446,  wickets=0,  strike_rate=148.8, batting_avg=37.2,
         economy=0.0, catches=18, fifties=2, hundreds=0, highest_score=88,  best_bowling='-'),
    dict(name="Jasprit Bumrah",    role="Bowler",      team="Mumbai Indians",
         nationality="Indian", age=30, base_price=200, current_price=200,
         matches=13, runs=12,   wickets=20, strike_rate=65.0,  batting_avg=0.0,
         economy=6.3, catches=4,  fifties=0, hundreds=0, highest_score=10,  best_bowling='3/14'),
    dict(name="Mohammed Shami",    role="Bowler",      team="Gujarat Titans",
         nationality="Indian", age=33, base_price=180, current_price=180,
         matches=17, runs=5,    wickets=28, strike_rate=35.2,  batting_avg=0.0,
         economy=7.9, catches=3,  fifties=0, hundreds=0, highest_score=8,   best_bowling='4/22'),
    dict(name="Yuzvendra Chahal",  role="Bowler",      team="Rajasthan Royals",
         nationality="Indian", age=33, base_price=100, current_price=100,
         matches=17, runs=8,    wickets=21, strike_rate=40.0,  batting_avg=0.0,
         economy=8.4, catches=6,  fifties=0, hundreds=0, highest_score=5,   best_bowling='3/27'),
    dict(name="Arshdeep Singh",    role="Bowler",      team="Punjab Kings",
         nationality="Indian", age=25, base_price=80,  current_price=80,
         matches=14, runs=10,   wickets=19, strike_rate=42.0,  batting_avg=0.0,
         economy=8.6, catches=5,  fifties=0, hundreds=0, highest_score=7,   best_bowling='4/9'),
    dict(name="Kuldeep Yadav",     role="Bowler",      team="Delhi Capitals",
         nationality="Indian", age=29, base_price=90,  current_price=90,
         matches=15, runs=6,    wickets=22, strike_rate=36.0,  batting_avg=0.0,
         economy=7.6, catches=7,  fifties=0, hundreds=0, highest_score=4,   best_bowling='4/14'),
    dict(name="Hardik Pandya",     role="All-Rounder", team="Mumbai Indians",
         nationality="Indian", age=30, base_price=150, current_price=150,
         matches=15, runs=216,  wickets=11, strike_rate=143.0, batting_avg=27.0,
         economy=9.1, catches=9,  fifties=0, hundreds=0, highest_score=46,  best_bowling='3/20'),
    dict(name="Ravindra Jadeja",   role="All-Rounder", team="Chennai Super Kings",
         nationality="Indian", age=35, base_price=140, current_price=140,
         matches=14, runs=289,  wickets=14, strike_rate=153.4, batting_avg=32.1,
         economy=7.7, catches=12, fifties=1, hundreds=0, highest_score=72,  best_bowling='3/17'),
    dict(name="Axar Patel",        role="All-Rounder", team="Delhi Capitals",
         nationality="Indian", age=30, base_price=110, current_price=110,
         matches=16, runs=310,  wickets=17, strike_rate=161.5, batting_avg=34.4,
         economy=7.9, catches=8,  fifties=2, hundreds=0, highest_score=64,  best_bowling='3/14'),
]


def seed_database():
    if Player.query.count() == 0:
        for p in PLAYERS:
            db.session.add(Player(**p))
        db.session.commit()
        print("✅ Database seeded with 16 IPL players.")
    else:
        print("ℹ️  Database already seeded.")


with app.app_context():
    db.create_all()
    seed_database()


# ─────────────────────────────────────────────────────────────────────────────
# AUTH DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        data     = request.get_json()
        email    = data.get('email', '').strip().lower()
        password = data.get('password', '')
        user     = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id']   = user.id
            session['username']  = user.username
            session['team_name'] = user.team_name or user.username
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401
    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    data      = request.get_json()
    username  = data.get('username', '').strip()
    email     = data.get('email', '').strip().lower()
    password  = data.get('password', '')
    team_name = data.get('team_name', '').strip()

    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered.'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already taken.'}), 400

    user = User(username=username, email=email, team_name=team_name or username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session['user_id']   = user.id
    session['username']  = user.username
    session['team_name'] = user.team_name
    return jsonify({'success': True})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/me')
def me():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session['username'],
                        'team_name': session['team_name']})
    return jsonify({'logged_in': False})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           username=session['username'],
                           team_name=session['team_name'])


@app.route('/api/players')
@login_required
def get_players():
    return jsonify([_player_summary(p) for p in Player.query.all()])


@app.route('/api/player/<int:player_id>')
@login_required
def get_player(player_id):
    p    = Player.query.get_or_404(player_id)
    bids = (Bid.query.filter_by(player_id=player_id)
            .order_by(Bid.timestamp.desc()).limit(5).all())
    data = _player_summary(p)
    data['bid_history'] = [
        {'bidder': b.bidder_name, 'amount': b.amount,
         'time': b.timestamp.strftime('%H:%M:%S')}
        for b in bids
    ]
    return jsonify(data)


@app.route('/api/bid', methods=['POST'])
@login_required
def place_bid():
    data        = request.get_json()
    player_id   = data.get('player_id')
    amount      = data.get('amount', 0)
    bidder_name = session.get('team_name', session.get('username', 'Unknown'))

    player = Player.query.get_or_404(player_id)
    if player.is_sold:
        return jsonify({'success': False, 'message': 'Player already sold!'}), 400
    if amount <= player.current_price:
        return jsonify({'success': False,
                        'message': f'Bid must be more than ₹{player.current_price}L'}), 400

    db.session.add(Bid(player_id=player_id, bidder_name=bidder_name, amount=amount))
    player.current_price = amount
    db.session.commit()

    socketio.emit('price_update', {
        'player_id':   player_id,
        'player_name': player.name,
        'new_price':   amount,
        'bidder':      bidder_name,
    })
    return jsonify({'success': True, 'new_price': amount})


@app.route('/api/sell', methods=['POST'])
@login_required
def sell_player():
    player_id = request.get_json().get('player_id')
    player    = Player.query.get_or_404(player_id)
    if player.is_sold:
        return jsonify({'success': False, 'message': 'Already sold.'}), 400
    top_bid = (Bid.query.filter_by(player_id=player_id)
               .order_by(Bid.amount.desc()).first())
    if not top_bid:
        return jsonify({'success': False, 'message': 'No bids placed yet.'}), 400
    player.is_sold = True
    player.sold_to = top_bid.bidder_name
    db.session.commit()
    socketio.emit('player_sold', {
        'player_id':   player_id,
        'player_name': player.name,
        'sold_to':     top_bid.bidder_name,
        'final_price': top_bid.amount,
    })
    return jsonify({'success': True, 'sold_to': top_bid.bidder_name,
                    'final_price': top_bid.amount})


@app.route('/api/reset', methods=['POST'])
@login_required
def reset_player():
    player_id = request.get_json().get('player_id')
    player    = Player.query.get_or_404(player_id)
    player.current_price = player.base_price
    player.is_sold       = False
    player.sold_to       = None
    Bid.query.filter_by(player_id=player_id).delete()
    db.session.commit()
    socketio.emit('price_update', {
        'player_id':   player_id,
        'player_name': player.name,
        'new_price':   player.base_price,
        'bidder':      'RESET',
    })
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _player_summary(p):
    return {
        'id': p.id, 'name': p.name, 'role': p.role, 'team': p.team,
        'nationality': p.nationality, 'age': p.age,
        'base_price': p.base_price, 'current_price': p.current_price,
        'is_sold': p.is_sold, 'sold_to': p.sold_to,
        'stats': {
            'matches': p.matches, 'runs': p.runs, 'wickets': p.wickets,
            'strike_rate': p.strike_rate, 'batting_avg': p.batting_avg,
            'economy': p.economy, 'catches': p.catches,
            'fifties': p.fifties, 'hundreds': p.hundreds,
            'highest_score': p.highest_score, 'best_bowling': p.best_bowling,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# SOCKET EVENTS
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    print(f"🔌 Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"❌ Client disconnected: {request.sid}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
