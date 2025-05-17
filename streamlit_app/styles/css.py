def get_navigation_button_styles():
    return """
        :root {
            --primary-color: #1e3a8a;
            --primary-hover: #1e40af;
            --text-primary: #111827;
            --text-secondary: #4b5563;
            --bg-primary: #ffffff;
            --bg-secondary: #f3f4f6;
            --card-bg: #ffffff;
            --border-color: #e5e7eb;
        }
        
        @media (prefers-color-scheme: dark) {
            :root {
                --text-primary: #f3f4f6;
                --text-secondary: #9ca3af;
                --bg-primary: #111827;
                --bg-secondary: #1f2937;
                --card-bg: #1f2937;
                --border-color: #374151;
            }
        }
        
        body {
            color: var(--text-primary);
            background-color: var(--bg-primary);
        }
        
        .stButton button {
            width: 100%;
            text-align: left;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            border: none;
            background-color: transparent;
            color: var(--text-primary);
            font-size: 1rem;
            transition: background-color 0.3s, color 0.3s;
        }
        .stButton button:hover {
            background-color: var(--bg-secondary) !important;
            border: none;
        }
        .stButton button[data-selected="true"] {
            background-color: var(--bg-secondary) !important;
            border-left: 4px solid var(--primary-color);
            color: var(--primary-color);
        }
    """

def get_sidebar_styles():
    return """
        section[data-testid="stSidebar"] {
            background-image: linear-gradient(180deg,#1e3a8a 0%,#1e40af 100%) !important;
            color: #ffffff !important;
        }
        section[data-testid="stSidebar"] .stMarkdown {
            color: #ffffff !important;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] h4,
        section[data-testid="stSidebar"] h5,
        section[data-testid="stSidebar"] h6 {
            color: #ffffff !important;
        }
    """

def get_metric_styles():
    return """
        [data-testid="stMetricValue"] {
            color: var(--text-primary) !important;
        }
        [data-testid="stMetricLabel"] {
            color: var(--text-secondary) !important;
        }
    """

def get_container_styles():
    return """
        .custom-container {
            background-color: var(--card-bg);
            padding: 1.5rem;
            border-radius: 0.75rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 0.75rem;
        }
        .stat-card {
            background-color: var(--bg-secondary);
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            border: 1px solid var(--border-color);
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--text-primary);
            margin-bottom: 0.25rem;
        }
        .stat-label {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
    """

def get_form_styles():
    return """
        div[data-testid="stForm"] {
            background: var(--card-bg);
            padding: 1.5rem;
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            margin-bottom: 1.5rem;
        }
        div[data-testid="stExpander"] {
            background: var(--card-bg);
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            margin-bottom: 1.5rem;
        }
        div[data-testid="stExpander"] > div {
            border: none !important;
        }
    """

def get_card_styles():
    return """
        .card {
            background: var(--card-bg);
            padding: 1.5rem;
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            margin-bottom: 1.5rem;
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
        /* Base text colors */
        body, .stTextInput > label, .stTextArea > label, .stSelectbox > label, 
        .stNumberInput > label, .stSlider > label, .stRadio > label, 
        .stCheckbox > label, .stMultiSelect > label, .stDateInput > label,
        .stTimeInput > label, .stFileUploader > label {
            color: var(--text-primary) !important;
        }
        
        /* Input fields */
        .stTextInput input, .stTextArea textarea, .stSelectbox select,
        .stNumberInput input, .stSlider div[role="slider"], .stRadio > div,
        .stCheckbox > div, .stMultiSelect > div, .stDateInput input,
        .stTimeInput input, .stFileUploader > div {
            background-color: var(--bg-primary) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
        }
        
        /* Input placeholders */
        ::placeholder {
            color: var(--text-secondary) !important;
            opacity: 0.7 !important;
        }
        
        /* Headers */
        .title {
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: var(--text-primary);
        }
        .subtitle {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: var(--text-primary);
        }
        .text-muted {
            color: var(--text-secondary);
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
            /* Base styles */
            {get_navigation_button_styles()}
            
            /* Component styles */
            {get_sidebar_styles()}
            {get_metric_styles()}
            {get_container_styles()}
            {get_form_styles()}
            {get_card_styles()}
            {get_button_styles()}
            {get_text_styles()}
            
            /* Dark mode overrides */
            @media (prefers-color-scheme: dark) {{
                /* Streamlit overrides */
                .stApp {{
                    background-color: var(--bg-primary) !important;
                    color: var(--text-primary) !important;
                }}
                
                /* Tables */
                .stDataFrame, .stTable {{
                    background-color: var(--card-bg) !important;
                    color: var(--text-primary) !important;
                }}
                
                /* Tabs */
                .stTabs [data-baseweb="tab"] {{
                    color: var(--text-secondary) !important;
                }}
                .stTabs [aria-selected="true"] {{
                    color: var(--primary-color) !important;
                }}
                
                /* Tooltips */
                .stTooltip, .stTooltipContent {{
                    background-color: var(--bg-secondary) !important;
                    color: var(--text-primary) !important;
                    border: 1px solid var(--border-color) !important;
                }}
            }}
        </style>
    """ 