# Canva Thumbnail Automation Setup

## Current Workflow (Manual)

1. **Generate Backgrounds**: Click "🎨 Generate Backgrounds (No Text)" in the Thumbnail Designer
2. **Download**: Download one of the 3 AI-generated background images (no text)
3. **Open Canva**: Click "🎨 Open Canva Template" or go to https://www.canva.com/create/youtube-thumbnails/
4. **Create Design**:
   - Set size to 1280x720 (YouTube thumbnail)
   - Upload the background image
   - Add text layer with your video title
   - Apply text styling (bold, shadows, safe zones)
5. **Export**: Download as PNG
6. **Upload**: Upload the final thumbnail to your library

## Future Automation (Canva API)

To fully automate this process, you'll need:

### Step 1: Get Canva API Access

1. Go to https://www.canva.com/developers/
2. Create a developer account
3. Create a new app
4. Get your API key

### Step 2: Add Credentials

Add to `.env` file:
```bash
CANVA_API_KEY=your_api_key_here
```

### Step 3: Create Canva Template

1. Create a YouTube thumbnail template (1280x720) in Canva
2. Add these layers:
   - Background image placeholder (full width/height)
   - Title text layer (safe zone: centered, 100px from edges)
   - Logo layer (bottom-left corner)
   - Any brand elements
3. Save as template
4. Get template ID

### Step 4: Update Code

Add template ID to `thumbnail_settings.json`:
```json
{
  "canvaTemplateId": "your_template_id_here"
}
```

### Automation Flow

Once configured, the system will:
1. Generate background with DALL-E (no text)
2. Upload background to Canva via API
3. Create design from template
4. Replace background layer with generated image
5. Update text layer with video title
6. Export final thumbnail (1280x720 PNG)
7. Download and save to library

### API Endpoints Required

- `POST /designs` - Create design from template
- `POST /uploads` - Upload background image
- `PATCH /designs/{id}` - Update design elements
- `GET /exports/{id}` - Export final thumbnail

## Benefits

- ✅ Perfect text spelling every time
- ✅ Consistent branding and safe zones
- ✅ One-click generation
- ✅ No manual Canva work needed

## Manual vs Automated

| Feature | Manual | Automated |
|---------|--------|-----------|
| Time | 5-10 min | 30 sec |
| Spelling | Perfect | Perfect |
| Consistency | Variable | Perfect |
| Effort | High | None |
| Cost | Free | API costs |

## Next Steps

For now, use the manual workflow. Once you're ready to automate:

1. Get Canva API access
2. Create and save a template
3. Add credentials to `.env`
4. Uncomment Canva API code in `api_server.py`
5. Test the automation
