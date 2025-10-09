# Avatar Auto-Matching by Voice Gender

The system **automatically selects the correct avatar** based on the TTS voice gender.

## How It Works

1. **Detects voice gender** from the `TTS_VOICE_NAME` in `.env`
2. **Finds matching avatar** with the same gender in `avatar_library.json`
3. **Falls back** to active avatar if no gender match found

## Voice Gender Detection

### Male Voices (indicators: J, B, Q, L, D, A)
- `en-US-Neural2-J` → Male ✓
- `en-US-Neural2-D` → Male ✓
- `en-US-Studio-Q` → Male ✓
- `en-US-News-L` → Male ✓
- `en-US-Neural2-A` → Male ✓

### Female Voices (everything else)
- `en-US-Neural2-C` → Female ✓
- `en-US-Neural2-F` → Female ✓
- `en-US-News-K` → Female ✓
- `en-GB-Neural2-A` → Female ✓

## Example Workflow

**Scenario 1: Male Voice**
```env
TTS_VOICE_NAME=en-US-News-L
```
→ System detects: **Male voice**
→ Searches for avatar with `"gender": "male"`
→ Selects: **David** or **Tim**

**Scenario 2: Female Voice**
```env
TTS_VOICE_NAME=en-US-News-K
```
→ System detects: **Female voice**
→ Searches for avatar with `"gender": "female"`
→ Selects: **Julie**

## Avatar Library Structure

```json
{
  "avatars": [
    {
      "name": "Julie",
      "gender": "female",
      "voice": "en-US-News-K",
      ...
    },
    {
      "name": "David",
      "gender": "male",
      "voice": "en-US-Studio-Q",
      ...
    }
  ]
}
```

## Where It Works

✅ **Video Generation** (`/create-video-enhanced`)
✅ **Post-Processing** (`/post-process-video`)
✅ **Both portrait and landscape videos**

## Fallback Behavior

If no avatar matches the voice gender:
1. Uses the first active avatar (`"active": true`)
2. Logs a warning: `[AVATAR] No {gender} avatar found, using active avatar`

## Manual Override

You can still manually set which avatar is active in the Avatar Manager:
- http://localhost:3000/avatar-manager.html

The system will only use the active avatar as a fallback if no gender match is found.

## Console Output

When auto-matching is active, you'll see:
```
[AVATAR] Auto-selecting avatar: Voice=en-US-News-L, Gender=male
```

This confirms the system detected the voice gender correctly.
