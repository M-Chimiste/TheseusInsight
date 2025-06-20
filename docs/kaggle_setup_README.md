# Kaggle API Setup for ArXiv Dataset Auto-Download

This guide explains how to set up Kaggle API credentials for automatic ArXiv dataset downloading when the OAI-PMH API is down.

## 🚀 Quick Setup

### Option 1: Environment Variables (Recommended)

1. **Get your Kaggle API credentials:**
   - Go to [kaggle.com](https://www.kaggle.com)
   - Click on your profile picture → Account
   - Scroll to "API" section
   - Click "Create New API Token"
   - This downloads `kaggle.json` with your credentials

2. **Set environment variables:**
   ```bash
   export KAGGLE_USERNAME="your_username"
   export KAGGLE_KEY="your_api_key_from_kaggle_json"
   export DEBUG=true  # Optional: for detailed logging
   ```

3. **Test the setup:**
   ```bash
   python example_kaggle_harvest.py
   ```

### Option 2: Kaggle JSON File

1. **Download your `kaggle.json`** (see step 1 above)

2. **Place it in the correct location:**
   ```bash
   # Create .kaggle directory
   mkdir -p ~/.kaggle
   
   # Move the downloaded file
   mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
   
   # Set proper permissions
   chmod 600 ~/.kaggle/kaggle.json
   ```

3. **Test the setup:**
   ```bash
   python example_kaggle_harvest.py
   ```

## 🎯 Usage Examples

### Automatic Fallback (Recommended)
```python
from theseus_insight.data_processing import UnifiedArxivHarvester

# This will try OAI-PMH first, auto-download Kaggle dataset if needed
with UnifiedArxivHarvester(
    category="cs",
    date_from="2024-12-01",
    date_until="2024-12-07",
    subcategories=["cs.ai", "cs.lg"],
    verbose=True
) as harvester:
    papers = harvester.harvest()
    print(f"Found {len(papers)} papers")
    # Dataset automatically cleaned up on exit
```

### Force Kaggle Mode
```bash
# Skip OAI-PMH entirely, use Kaggle dataset only
export FORCE_KAGGLE=true
python your_script.py
```

### Manual Dataset Path
```bash
# Use existing dataset file
export KAGGLE_ARXIV_PATH="/path/to/arxiv-metadata-oai-snapshot.json"
python your_script.py
```

## ⚙️ Environment Variables

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `KAGGLE_USERNAME` | Your Kaggle username | - | `"john_doe"` |
| `KAGGLE_KEY` | Your Kaggle API key | - | `"abc123def456..."` |
| `KAGGLE_ARXIV_PATH` | Path to existing dataset | `"data/arxiv-metadata-oai-snapshot.json"` | `"/tmp/arxiv.json"` |
| `FORCE_KAGGLE` | Skip OAI-PMH, use Kaggle only | `false` | `"true"` |
| `AUTO_DOWNLOAD` | Enable auto-download | `true` | `"false"` |
| `DEBUG` | Detailed logging | `false` | `"true"` |

## 🔍 Troubleshooting

### "Kaggle API not found"
```bash
# Install Kaggle API
pip install kaggle
```

### "No Kaggle credentials found"
- Check your `kaggle.json` file exists at `~/.kaggle/kaggle.json`
- Or set `KAGGLE_USERNAME` and `KAGGLE_KEY` environment variables
- Verify your API token is active on Kaggle

### "Dataset download failed"
- Check your internet connection
- Verify your Kaggle account has dataset access
- Make sure you have enough disk space (~3GB)

### "Permission denied"
```bash
# Fix kaggle.json permissions
chmod 600 ~/.kaggle/kaggle.json
```

## 📊 Dataset Information

- **Dataset**: [Cornell University ArXiv](https://www.kaggle.com/datasets/Cornell-University/arxiv)
- **Size**: ~3.1 GB compressed
- **Records**: 1.7+ million papers
- **Format**: JSON Lines (one paper per line)
- **Updates**: Periodically updated by Cornell

## 🧹 Automatic Cleanup

The unified harvester automatically:
- ✅ Downloads dataset to temporary directory when needed
- ✅ Processes your query
- ✅ Cleans up downloaded files when finished
- ✅ Handles errors gracefully with proper cleanup

## 🛡️ Security Notes

- Keep your `kaggle.json` file secure (permissions 600)
- Don't commit API keys to version control
- Use environment variables in production
- Regularly rotate your API keys

## 📚 Advanced Usage

### Disable Auto-Download
```bash
export AUTO_DOWNLOAD=false
```

### Custom Download Path
```python
harvester = UnifiedArxivHarvester(
    category="cs",
    date_from="2024-12-01", 
    date_until="2024-12-07",
    kaggle_dataset_path="/custom/path/arxiv.json"
)
```

### Context Manager for Guaranteed Cleanup
```python
with UnifiedArxivHarvester(...) as harvester:
    papers = harvester.harvest()
    # Process papers here
# Automatic cleanup happens here
``` 