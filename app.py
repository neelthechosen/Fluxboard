import os
from flask import Flask, render_template, request, jsonify
import requests
import praw
from textblob import TextBlob
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# API Configuration
COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY', 'CG-oUpG62o22KvJGpmC99XE5tRz')
REDDIT_SECRET = os.getenv('REDDIT_SECRET', 'oEQGXpNxjQ7WIOwBz1vv9rVMTKNFeQ')

# CoinGecko API base URL
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Reddit API setup - Using environment variables for security
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID', 'your_client_id_here'),
    client_secret=REDDIT_SECRET,
    user_agent="crypto_screener_v1"
)

class CoinGeckoAPI:
    def __init__(self):
        self.base_url = COINGECKO_BASE_URL
        self.headers = {
            "x-cg-demo-api-key": COINGECKO_API_KEY
        }
    
    def get_trending_coins(self):
        """Get trending coins from CoinGecko"""
        try:
            url = f"{self.base_url}/search/trending"
            response = requests.get(url, headers=self.headers)
            data = response.json()
            
            trending_coins = []
            for coin in data['coins'][:10]:
                coin_data = coin['item']
                trending_coins.append({
                    'id': coin_data['id'],
                    'name': coin_data['name'],
                    'symbol': coin_data['symbol'].upper(),
                    'market_cap_rank': coin_data['market_cap_rank'],
                    'thumb': coin_data['thumb']
                })
            return trending_coins
        except Exception as e:
            print(f"Error fetching trending coins: {e}")
            return []
    
    def get_top_gainers_losers(self):
        """Get top gainers and losers (24h)"""
        try:
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 100,
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'
            }
            response = requests.get(url, headers=self.headers, params=params)
            coins = response.json()
            
            # Sort by price change percentage
            sorted_coins = sorted(coins, key=lambda x: x.get('price_change_percentage_24h', 0) or 0, reverse=True)
            
            gainers = sorted_coins[:10]
            losers = sorted_coins[-10:]
            
            return gainers, losers
        except Exception as e:
            print(f"Error fetching gainers/losers: {e}")
            return [], []
    
    def get_coins_screener(self, filters=None):
        """Get coins with filtering options"""
        try:
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 250,
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h,7d,30d'
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            coins = response.json()
            
            # Apply filters
            if filters:
                if filters.get('search'):
                    search_term = filters['search'].lower()
                    coins = [coin for coin in coins if search_term in coin['name'].lower() or 
                            search_term in coin['symbol'].lower()]
                
                # Additional filtering can be added here for market cap, volume, etc.
                if filters.get('min_market_cap'):
                    coins = [coin for coin in coins if coin.get('market_cap', 0) >= int(filters['min_market_cap'])]
                if filters.get('max_market_cap'):
                    coins = [coin for coin in coins if coin.get('market_cap', 0) <= int(filters['max_market_cap'])]
                if filters.get('min_volume'):
                    coins = [coin for coin in coins if coin.get('total_volume', 0) >= int(filters['min_volume'])]
                if filters.get('min_percent_change'):
                    coins = [coin for coin in coins if coin.get('price_change_percentage_24h', 0) >= float(filters['min_percent_change'])]
            
            return coins
        except Exception as e:
            print(f"Error in coin screener: {e}")
            return []
    
    def get_historical_data(self, coin_id, days=30):
        """Get historical price data for charts"""
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'daily' if days > 1 else 'hourly'
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            data = response.json()
            
            prices = data['prices']
            timestamps = [datetime.fromtimestamp(price[0]/1000) for price in prices]
            values = [price[1] for price in prices]
            
            return timestamps, values
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            return [], []

class SentimentAnalyzer:
    def __init__(self):
        self.positive_keywords = {
            'bullish', 'moon', 'rocket', 'buy', 'long', 'profit', 'gain', 'growth',
            'success', 'win', 'positive', 'good', 'great', 'amazing', 'awesome',
            'breakout', 'pump', 'surge', 'rally', 'recovery'
        }
        self.negative_keywords = {
            'bearish', 'dump', 'sell', 'short', 'loss', 'drop', 'crash', 'scam',
            'fraud', 'warning', 'danger', 'bad', 'terrible', 'awful', 'failure',
            'collapse', 'plunge', 'decline', 'correction', 'fud'
        }
    
    def analyze_sentiment(self, text):
        """Analyze sentiment using both TextBlob and keyword analysis"""
        if not text:
            return 'neutral'
            
        text_lower = text.lower()
        
        # Keyword-based analysis
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)
        
        # TextBlob analysis
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
        except:
            polarity = 0
        
        # Combine both approaches
        if positive_count > negative_count:
            keyword_sentiment = 'positive'
        elif negative_count > positive_count:
            keyword_sentiment = 'negative'
        else:
            keyword_sentiment = 'neutral'
        
        # Final sentiment determination
        if polarity > 0.1 or keyword_sentiment == 'positive':
            return 'positive'
        elif polarity < -0.1 or keyword_sentiment == 'negative':
            return 'negative'
        else:
            return 'neutral'

# Initialize API clients
coingecko = CoinGeckoAPI()
sentiment_analyzer = SentimentAnalyzer()

@app.route('/')
def index():
    """Dashboard homepage"""
    trending_coins = coingecko.get_trending_coins()
    gainers, losers = coingecko.get_top_gainers_losers()
    
    return render_template('index.html', 
                         trending_coins=trending_coins,
                         gainers=gainers,
                         losers=losers)

@app.route('/screener')
def screener():
    """Coin screener page"""
    filters = {
        'search': request.args.get('search', ''),
        'min_market_cap': request.args.get('min_market_cap'),
        'max_market_cap': request.args.get('max_market_cap'),
        'min_volume': request.args.get('min_volume'),
        'min_percent_change': request.args.get('min_percent_change')
    }
    
    coins = coingecko.get_coins_screener(filters)
    
    return render_template('screener.html', coins=coins, filters=filters)

@app.route('/sentiment')
def sentiment():
    """Reddit sentiment analysis page"""
    coin_query = request.args.get('coin', 'BTC')
    posts = []
    sentiment_stats = {'positive': 0, 'negative': 0, 'neutral': 0}
    
    if coin_query:
        # Search Reddit posts
        subreddits = ['CryptoCurrency', 'Bitcoin', 'Ethereum', 'Solana', 'CryptoMoonShots']
        
        for subreddit_name in subreddits:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                
                for post in subreddit.search(coin_query, limit=3, time_filter='week'):
                    sentiment_result = sentiment_analyzer.analyze_sentiment(post.title)
                    sentiment_stats[sentiment_result] += 1
                    
                    posts.append({
                        'title': post.title,
                        'url': post.url,
                        'upvotes': post.score,
                        'timestamp': datetime.fromtimestamp(post.created_utc),
                        'subreddit': subreddit_name,
                        'sentiment': sentiment_result
                    })
                    
                    if len(posts) >= 15:  # Limit total posts
                        break
                        
            except Exception as e:
                print(f"Error fetching from r/{subreddit_name}: {e}")
                continue
    
    # Calculate sentiment percentages
    total_posts = len(posts)
    if total_posts > 0:
        bullish_pct = (sentiment_stats['positive'] / total_posts) * 100
        bearish_pct = (sentiment_stats['negative'] / total_posts) * 100
        neutral_pct = (sentiment_stats['neutral'] / total_posts) * 100
    else:
        bullish_pct = bearish_pct = neutral_pct = 0
    
    return render_template('sentiment.html',
                         posts=posts[:10],
                         coin_query=coin_query,
                         bullish_pct=bullish_pct,
                         bearish_pct=bearish_pct,
                         neutral_pct=neutral_pct,
                         total_posts=total_posts)

@app.route('/charts')
def charts():
    """Charts page"""
    coin_id = request.args.get('coin', 'bitcoin')
    timeframe = request.args.get('timeframe', '30')
    
    timestamps, prices = coingecko.get_historical_data(coin_id, int(timeframe))
    
    # Create Plotly chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=prices,
        mode='lines',
        name='Price',
        line=dict(color='#00D395', width=2)
    ))
    
    fig.update_layout(
        title=f'Price Chart - {timeframe} days',
        xaxis_title='Date',
        yaxis_title='Price (USD)',
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white')
    )
    
    chart_html = fig.to_html(full_html=False)
    
    return render_template('charts.html', 
                         chart_html=chart_html,
                         selected_coin=coin_id,
                         selected_timeframe=timeframe)

@app.route('/api/search-coins')
def search_coins():
    """API endpoint for coin search"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify([])
    
    # Get coins and filter by search query
    coins = coingecko.get_coins_screener()
    filtered_coins = [
        coin for coin in coins 
        if query in coin['name'].lower() or query in coin['symbol'].lower()
    ][:10]  # Limit results
    
    return jsonify(filtered_coins)

if __name__ == '__main__':
    app.run(debug=True)
