#!/bin/bash
# Script to deploy migrations to Heroku

echo "🚀 Deploying migrations to Heroku..."
echo ""

# Step 1: Push code to Heroku
echo "📤 Step 1: Pushing code to Heroku..."
git add .
git status

read -p "Do you want to commit and push? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    git commit -m "Add full_name field and leaderboard pagination"
    git push heroku main

    echo ""
    echo "✅ Code pushed to Heroku"
else
    echo "❌ Cancelled"
    exit 1
fi

# Step 2: Run migrations
echo ""
echo "📊 Step 2: Running migrations..."
heroku run python manage.py migrate

echo ""
echo "✅ Migrations applied!"
echo ""
echo "🔄 Step 3: Restarting bot..."
heroku ps:restart

echo ""
echo "✅ Done! Check logs with: heroku logs --tail"
