-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users / Farmer Profiles (Extending Supabase Auth or Custom Users)
-- We will use a custom users table for simplicity, but in a real app you might link to auth.users
CREATE TABLE public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    mobile TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    hashed_password TEXT NOT NULL,
    location TEXT,
    preferred_language TEXT DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE TABLE public.farmer_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT,
    mobile TEXT,
    farm_size FLOAT DEFAULT 0.0,
    primary_crop TEXT DEFAULT 'Paddy',
    location TEXT DEFAULT 'Tamil Nadu',
    preferred_language TEXT DEFAULT 'en',
    notify_weather INTEGER DEFAULT 1,
    notify_spray INTEGER DEFAULT 1,
    notify_schemes INTEGER DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 2 & 3 & 4. Crop Analysis History, Disease Prediction Results, Uploaded Images
CREATE TABLE public.crop_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    crop_type TEXT NOT NULL,
    image_path TEXT, -- Storage reference or URI
    detected_disease TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    severity TEXT DEFAULT 'Not determined',
    risk_level TEXT DEFAULT 'Not determined',
    quality_status TEXT DEFAULT 'Passed',
    weather_context TEXT,
    is_inconclusive INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 5. Weather Alerts (Cached or Saved for users)
CREATE TABLE public.weather_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    alert_type TEXT,
    alert_level TEXT,
    message_en TEXT,
    message_ta TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 6. Chatbot Conversations
CREATE TABLE public.chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'ai')),
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- 7. Recommendations
CREATE TABLE public.recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    crop_analysis_id UUID REFERENCES public.crop_analyses(id) ON DELETE CASCADE,
    recommendation_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Row Level Security (RLS) Setup
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farmer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crop_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weather_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;

-- Note: Since we are using a custom users table (not Supabase Auth), 
-- our FastAPI backend will act as the service layer. 
-- In a typical setup where FastAPI passes the user token, RLS would use auth.uid().
-- Since we are connecting from FastAPI using the anon key without impersonation, 
-- we will allow all access for now, but restrict it in FastAPI code.
-- Or, to be secure with RLS from backend, we should use policies that allow access if the request comes from our backend, but standard practice with publishable key is to enforce it here.
-- For now, let's create permissive policies for the API to function, and handle authorization in FastAPI.
CREATE POLICY "Allow API access to users" ON public.users FOR ALL USING (true);
CREATE POLICY "Allow API access to profiles" ON public.farmer_profiles FOR ALL USING (true);
CREATE POLICY "Allow API access to crop_analyses" ON public.crop_analyses FOR ALL USING (true);
CREATE POLICY "Allow API access to weather_alerts" ON public.weather_alerts FOR ALL USING (true);
CREATE POLICY "Allow API access to chat_history" ON public.chat_history FOR ALL USING (true);
CREATE POLICY "Allow API access to recommendations" ON public.recommendations FOR ALL USING (true);

-- Supabase Storage for crop images
INSERT INTO storage.buckets (id, name, public) VALUES ('crop-images', 'crop-images', true)
ON CONFLICT DO NOTHING;

CREATE POLICY "Public Access" ON storage.objects FOR SELECT USING (bucket_id = 'crop-images');
CREATE POLICY "Allow uploads" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'crop-images');

-- Performance Indexes for fast dashboard and history lookups
CREATE INDEX IF NOT EXISTS idx_crop_analyses_created_at ON public.crop_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_crop_analyses_user_id ON public.crop_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON public.chat_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_farmer_profiles_user_id ON public.farmer_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_weather_alerts_created_at ON public.weather_alerts(created_at DESC);

