# Interface Agent (CLI/UI)

## Agent Role
**Primary Responsibility**: Design simple UI/CLI for indexing, search, and system status as per requirements.

## Core Requirements Addressed

### CLI Interface Implementation
- **Easy Indexing**: `python -m src.main index --origin <URL> --depth <k>`
- **Easy Search**: `python -m src.main search --query <text>`
- **System Status**: `python -m src.main status` shows indexing progress, queue depth, backpressure

### Web Dashboard (Bonus Interface)
- **URL**: http://127.0.0.1:8888
- **Features**: Real-time metrics, interactive search, system monitoring
- **Design**: Minimalist, professional interface

## Technical Contributions

### CLI Design - Core Requirements
```bash
# REQUIREMENT: Easy to initiate indexing
python -m src.main index --origin "https://example.com" --depth 2

# REQUIREMENT: Easy to search  
python -m src.main search --query "python tutorial"

# REQUIREMENT: View system state
python -m src.main status          # Shows indexing progress
python -m src.main stats --detailed # Queue depth, backpressure status
```

### System Status Monitoring
```python
# Shows exactly what assignment requires:
def display_status():
    return {
        'indexing_progress': f"{pages_crawled}/{max_pages}",
        'queue_depth': len(url_queue),
        'backpressure_status': 'active' if queue_depth > threshold else 'normal',
        'crawl_rate': 'pages_per_minute',
        'active_workers': concurrent_requests
    }
```

### Progress Tracking Features
- **Indexing Progress**: Real-time page count and completion percentage
- **Queue Depth**: Current URL queue size and trends
- **Backpressure Status**: Active/normal status with threshold monitoring
- **Worker Status**: Number of active concurrent requests
- **Error Rates**: Failed requests and retry statistics

## Interface Design Principles

### Simplicity (As Required)
- **Single Commands**: One command for each operation (index, search, status)
- **Minimal Arguments**: Only essential parameters required
- **Clear Output**: Formatted tables and progress indicators
- **Error Handling**: Helpful error messages with suggestions

### Real-time Updates
- **Live Progress**: Progress bars during indexing operations
- **Status Refresh**: Auto-updating system metrics
- **Queue Monitoring**: Real-time queue depth and backpressure status
- **Search Results**: Immediate feedback with formatted output

## Web Dashboard (Additional Interface)

### Real-time System Monitoring
- **Live Metrics**: Auto-refreshing every 30 seconds
- **Interactive Search**: Web form with formatted results
- **Professional Design**: Minimalist, Figma-inspired interface
- **Mobile Responsive**: Works on all devices

### Dashboard Features
```javascript
// Real-time status display
{
  "total_pages_crawled": 1247,
  "queue_depth": 23,
  "backpressure_status": "normal",
  "crawl_rate": "1,150 pages/min",
  "last_update": "2 seconds ago"
}
```

## System State Visibility

### Required Status Information
1. **Indexing Progress**: Current page count and crawl status
2. **Queue Depth**: Number of URLs waiting to be processed
3. **Backpressure Status**: System load management status
4. **Performance Metrics**: Crawl rate, success rate, error count
5. **Worker Status**: Active concurrent requests and their status

### User Experience Design
- **Rich Terminal Output**: Colored text, progress bars, formatted tables
- **Web Interface**: Professional dashboard with live updates
- **Consistent Commands**: Intuitive command structure
- **Help System**: Built-in help for all commands

## Integration with Core Functions

### Indexing Interface
- **Parameter Validation**: Ensures origin URL and depth are valid
- **Progress Display**: Real-time crawling progress with rich formatting
- **Status Updates**: Live queue depth and backpressure monitoring
- **Error Reporting**: Clear error messages with recovery suggestions

### Search Interface
- **Query Processing**: Accepts text queries and validates input
- **Result Formatting**: Multiple output formats (table, JSON, YAML)
- **Performance Display**: Shows search latency and result count
- **Interactive Features**: Web-based search with clickable results

## Requirements Fulfillment
✅ **Easy Indexing**: Simple CLI command with required parameters
✅ **Easy Search**: Simple CLI command with query input
✅ **System Status**: Shows indexing progress, queue depth, backpressure
✅ **Simple Interface**: Minimal, intuitive command structure
✅ **Bonus Web UI**: Professional web dashboard with real-time features
✅ **State Persistence**: Resumable operations after interruption