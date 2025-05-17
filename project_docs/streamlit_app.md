# Theseus Insight Streamlit Application

## Overview
Theseus Insight is a Streamlit-based web application designed for research paper analysis and content generation. The application provides an intuitive interface for managing research papers, generating newsletters, creating podcasts, and tracking research activities.

## Application Structure

```
streamlit_app/
├── app.py              # Main application entry point
├── styles/
│   └── css.py         # Centralized CSS styling
├── views/
│   ├── settings.py    # Settings page configuration
│   ├── newsletter.py  # Newsletter builder
│   ├── podcast.py     # Podcast content manager
│   ├── papers.py      # Paper ratings and analysis
│   └── runs.py        # Activity logging
└── api_utils.py       # API utilities and helpers
```

## Core Features

### 1. Navigation System
- Custom sidebar navigation with modern styling
- Icon-based menu items (⚙️, 📰, 🎙️, 📄, 📊)
- Session state management for page routing
- Active page highlighting

### 2. Settings Management (⚙️)
- API configuration
  - API key management
  - Environment selection (Development/Staging/Production)
- Model settings
  - Language model selection (GPT-4, GPT-3.5-Turbo, Claude-2, Claude-3)
  - Temperature control
  - Token limits
- Display preferences
  - Theme selection (Light/Dark/System)
- Advanced configurations
  - Batch processing settings
  - Token management

### 3. Newsletter Builder (📰)
- Newsletter configuration
  - Title and description
  - Issue numbering
  - Publication scheduling
- Section management
  - Multiple section types (Featured Papers, Industry News, etc.)
  - Content organization
  - Importance rating system
- Quick actions
  - Preview generation
  - HTML export
  - Test email functionality

### 4. Podcast Builder (🎙️)
- Episode planning
- Content structuring
- Audio management
- Publication scheduling

### 5. Paper Ratings (📄)
- Paper analysis
- Rating system
- Category organization
- Search functionality

### 6. Run Log (📊)
- Activity tracking
- Performance metrics
- Status monitoring
- Error logging

## Styling System

The application uses a centralized styling system (`styles/css.py`) with modular components:

1. **Navigation Styles**
   - Button styling
   - Active state highlighting
   - Hover effects

2. **Sidebar Design**
   - Gradient background
   - Consistent typography
   - Metric displays

3. **Form Components**
   - Modern input fields
   - Card-like containers
   - Shadow effects

4. **Container Layouts**
   - Grid systems
   - Responsive design
   - Spacing utilities

5. **Typography**
   - Consistent text hierarchy
   - Color schemes
   - Status indicators

## State Management

The application uses Streamlit's session state for:
- Current page tracking
- Form data persistence
- User preferences
- Content caching

## Best Practices

1. **Code Organization**
   - Modular view structure
   - Centralized styling
   - Clear component separation

2. **User Experience**
   - Consistent navigation
   - Clear feedback messages
   - Intuitive layouts

3. **Performance**
   - Efficient state management
   - Optimized styling
   - Minimal reloads

## Development Guidelines

1. **Adding New Features**
   - Create new views in the `views/` directory
   - Update navigation in `app.py`
   - Add corresponding styles in `styles/css.py`

2. **Styling Updates**
   - Use the centralized CSS system
   - Follow existing color schemes
   - Maintain consistency

3. **State Management**
   - Use session state for persistence
   - Clear state when necessary
   - Handle edge cases

## Future Enhancements

1. **Planned Features**
   - Enhanced analytics
   - Export options
   - Integration capabilities

2. **Potential Improvements**
   - Additional customization options
   - Extended API functionality
   - Advanced search features

## Technical Requirements

- Python 3.7+
- Streamlit
- Required packages in `requirements.txt`
- API access credentials

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. Run the application:
   ```bash
   streamlit run streamlit_app/app.py
   ```

## Contributing

1. Follow the existing code structure
2. Maintain consistent styling
3. Document new features
4. Test thoroughly before submitting changes

## Support

For issues and feature requests, please use the issue tracker or contact the development team. 