import requests
import json

def get_weather(api_key, city_code):
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": api_key,
        "city": city_code
    }
    response = requests.get(url, params=params)
    data = json.loads(response.text)
    
    if response.status_code == 200 and data.get('lives'):
        weather_info = data['lives'][0]
        weather_report = (
            f"Province: {weather_info['province']}\n"
            f"City: {weather_info['city']}\n"
            f"Weather: {weather_info['weather']}\n"
            f"Temperature: {weather_info['temperature']}°C\n"
            f"Wind Direction: {weather_info['winddirection']}\n"
            f"Wind Power: {weather_info['windpower']}\n"
            f"Humidity: {weather_info['humidity']}%\n"
            f"Report Time: {weather_info['reporttime']}"
        )
        return weather_report
    else:
        return "Failed to retrieve weather information."
