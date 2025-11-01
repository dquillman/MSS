# Button Color Standards

This document defines the standard button color classes to ensure consistency across all pages in the MSS Studio application.

## Overview

All buttons should use semantic CSS classes instead of inline styles or hardcoded colors. This ensures:
- **Consistency**: Same action types use the same colors everywhere
- **Maintainability**: Change colors in one place (studio.css)
- **Accessibility**: Consistent visual language for users
- **Scalability**: Easy to add new button types

## Standard Button Classes

### `.btn-primary` (Blue)
**Color**: `#2563eb` → `#3b82f6` on hover  
**Use for**: 
- Main actions
- Primary navigation buttons
- Default actions when no specific semantic meaning applies
- Studio, Dashboard, Settings navigation

**Example**:
```html
<button class="btn btn-primary">Studio</button>
<button class="btn btn-primary">Save Changes</button>
```

---

### `.btn-success` (Green)
**Color**: `#34d399` → `#16a34a` on hover  
**Use for**: 
- Positive/confirmatory actions
- Save operations
- Approve/Confirm actions
- Submit forms
- Success-related workflows

**Example**:
```html
<button class="btn btn-success">💾 Save</button>
<button class="btn btn-success">✅ Approve & Publish</button>
```

---

### `.btn-danger` (Red)
**Color**: `#ef4444` → `#dc2626` on hover  
**Use for**: 
- Destructive/dangerous actions
- Delete operations
- Remove/Clear actions
- Logout
- Reset operations

**Example**:
```html
<button class="btn btn-danger">Delete</button>
<button class="btn btn-danger">Clear Topic</button>
<button class="btn btn-danger">Logout</button>
```

---

### `.btn-warning` (Orange/Yellow)
**Color**: `#f59e0b` → `#d97706` on hover  
**Use for**: 
- Warning actions
- Cautionary operations
- Attention-requiring actions

**Example**:
```html
<button class="btn btn-warning">⚠️ Warning Action</button>
```

---

### `.btn-secondary` (Gray)
**Color**: `#334` → `#445` on hover  
**Use for**: 
- Secondary actions
- Cancel buttons
- Less important actions
- Alternative options

**Example**:
```html
<button class="btn btn-secondary">Cancel</button>
<button class="btn btn-secondary">← Back</button>
```

---

### `.btn-info` (Cyan)
**Color**: `#0891b2` → `#0e7490` on hover  
**Use for**: 
- Informational actions
- Export/Import operations
- Download/Upload operations
- Data-related actions

**Example**:
```html
<button class="btn btn-info">⬇ Export</button>
<button class="btn btn-info">⬆ Import</button>
```

---

## Base Button Class

All buttons must include the base `.btn` class along with a color variant:

```html
<!-- Correct -->
<button class="btn btn-primary">Click Me</button>
<button class="btn btn-success">Save</button>

<!-- Incorrect - Missing base class -->
<button class="btn-success">Save</button>
```

The base `.btn` class provides:
- Padding, border-radius, font-weight
- Hover/active states
- Disabled state styling
- Transitions

## Migration Guide

### Before (Inline Styles - DON'T USE)
```html
<button class="btn" style="background:#22c55e; border-color:#22c55e;">Save</button>
<button class="btn" style="background:#ef4444; border-color:#ef4444;">Delete</button>
```

### After (Semantic Classes - USE THIS)
```html
<button class="btn btn-success">Save</button>
<button class="btn btn-danger">Delete</button>
```

### Color Mapping Reference

| Old Inline Color | New Class | Use Case |
|-----------------|-----------|----------|
| `#22c55e` (green) | `.btn-success` | Save, Approve, Confirm |
| `#3b82f6` or `#2563eb` (blue) | `.btn-primary` | Main actions, Navigation |
| `#ef4444` or `#dc2626` (red) | `.btn-danger` | Delete, Clear, Logout |
| `#f59e0b` (orange) | `.btn-warning` | Warnings |
| `#334` (gray) | `.btn-secondary` | Cancel, Secondary actions |
| `#0891b2` (cyan) | `.btn-info` | Export, Import |
| `#7c3aed` (purple) | `.btn-primary` or custom | Settings, Special (evaluate case-by-case) |
| `#FF0000` (bright red) | `.btn-danger` | YouTube-specific actions |

## Special Cases

### Platform-Specific Buttons
Some buttons may need platform branding colors (e.g., YouTube red). For these cases:
1. First check if `.btn-danger` is semantically appropriate
2. If not, create a platform-specific variant in `studio.css`
3. Document the variant in this file

### Custom Colors
Avoid creating new button colors unless absolutely necessary. If you need a new color:
1. Check if an existing semantic class fits
2. If creating a new class, add it to `studio.css` following the existing pattern
3. Update this documentation

## Best Practices

1. **Always use semantic classes**: Never use inline `style="background:..."` for button colors
2. **Combine classes**: Use `class="btn btn-success"` not just `class="btn-success"`
3. **Consistent usage**: Same action type = same button color across all pages
4. **Accessibility**: Ensure sufficient contrast (button classes already handle this)
5. **Document exceptions**: If you must deviate, document why

## Quick Reference

```
Primary Action     → .btn-primary  (Blue)
Save/Approve       → .btn-success  (Green)
Delete/Logout      → .btn-danger   (Red)
Warning            → .btn-warning (Orange)
Cancel/Secondary   → .btn-secondary (Gray)
Export/Import      → .btn-info     (Cyan)
```

## Files to Update

All HTML files in `web/topic-picker-standalone/` should be migrated to use these standard classes. The following files have been identified as having inline button styles:
- studio.html
- preview.html
- settings.html
- thumbnail-manager.html
- intro-outro.html
- edit-topic.html
- avatar-manager.html
- channel-manager.html
- index.html
- And others...

