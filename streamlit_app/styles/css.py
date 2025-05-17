def get_navigation_button_styles():
    return """
        .stButton button {
            width: 100%;
            text-align: left;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            border: none;
            background-color: transparent;
            color: #000;
            font-size: 1rem;
            transition: background-color 0.3s;
        }
        .stButton button:hover {
            background-color: rgba(255, 255, 255, 0.3) !important;
            border: none;
        }
        .stButton button[data-selected="true"] {
            background-color: rgba(255, 255, 255, 0.4) !important;
            border-left: 4px solid #1e3a8a;
            color: #1e3a8a;
        }
    """

def get_sidebar_styles():
    return """
        section[data-testid="stSidebar"] {
            background-image: linear-gradient(180deg,#60a5fa 0%,#93c5fd 100%);
            color: #000;
        }
        section[data-testid="stSidebar"] .stMarkdown {
            color: #000;
        }
    """

def get_metric_styles():
    return """
        [data-testid="stMetricValue"] {
            color: #000 !important;
        }
        [data-testid="stMetricLabel"] {
            color: rgba(0, 0, 0, 0.8) !important;
        }
    """

def get_container_styles():
    return """
        .custom-container {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 0.75rem;
        }
        .stat-card {
            background-color: rgba(255, 255, 255, 0.2);
            padding: 0.75rem;
            border-radius: 0.4rem;
            text-align: center;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #000;
        }
        .stat-label {
            color: rgba(0, 0, 0, 0.8);
            font-size: 0.9rem;
        }
    """

def get_form_styles():
    return """
        div[data-testid="stForm"] {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }
        div[data-testid="stExpander"] {
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }
    """

def get_card_styles():
    return """
        .card {
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
    """

def get_button_styles():
    return """
        .primary-button {
            background-color: #2563eb;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .primary-button:hover {
            background-color: #1d4ed8;
        }
        .secondary-button {
            background-color: #e5e7eb;
            color: #374151;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .secondary-button:hover {
            background-color: #d1d5db;
        }
    """

def get_text_styles():
    return """
        .title {
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #111827;
        }
        .subtitle {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: #374151;
        }
        .text-muted {
            color: #6b7280;
        }
        .success-text {
            color: #059669;
        }
        .error-text {
            color: #dc2626;
        }
    """

def apply_all_styles():
    return f"""
        <style>
            {get_navigation_button_styles()}
            {get_sidebar_styles()}
            {get_metric_styles()}
            {get_container_styles()}
            {get_form_styles()}
            {get_card_styles()}
            {get_button_styles()}
            {get_text_styles()}
        </style>
    """ 