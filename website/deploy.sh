#!/bin/bash
# VisionNodes Website Deployment Script for GitHub Pages

echo "🚀 Building VisionNodes Studio Website..."
npm install
npm run build

echo "📂 Preparing dist folder..."
# GitHub Pages needs a .nojekyll file to avoid ignoring underscore folders
touch dist/.nojekyll

echo "✅ Build complete! You can now upload the 'dist' folder content to your gh-pages branch."
echo "Suggested command: npx gh-pages -d dist"
