import argparse
from theseus_insight import TheseusInsight

def parse_args():
    parser = argparse.ArgumentParser(description="Run Theseus Insight with custom configurations")
    
    # Add arguments with current defaults
    parser.add_argument("--research-interests-path", type=str, 
                       default="config/research_interests.txt",
                       help="Path to research interests file")
    
    parser.add_argument("--n-days", type=int, default=7,
                       help="Number of days to look back for papers")
    
    parser.add_argument("--top-n", type=int, default=5,
                       help="Number of top papers to return")
    
    parser.add_argument("--orchestration-config", type=str,
                       default="config/orchestration.json",
                       help="Path to orchestration config file for multiple models")
    
    parser.add_argument("--receiver-address", type=str, default=None,
                       help="Email address to receive notifications")
    
    parser.add_argument("--max-new-tokens", type=int, default=1024,
                       help="Maximum number of new tokens to generate")
    
    parser.add_argument("--temperature", type=float, default=0.1,
                       help="Temperature for text generation")
    
    parser.add_argument("--cosine-similarity-threshold", type=float, default=0.5,
                       help="Threshold for cosine similarity")
    
    parser.add_argument("--db-saving", type=bool, default=True,
                       help="Whether to save results to database")
    
    parser.add_argument("--db-url", "--data-path", dest="db_url", type=str,
                       default="postgresql://postgres:postgres@localhost:5432/theseus",
                       help="Database connection URL")
    
    parser.add_argument("--verbose", type=bool, default=True,
                       help="Whether to print verbose output")
    
    parser.add_argument("--start-date", type=str, default=None,
                       help="Start date for paper retrieval")
    
    parser.add_argument("--end-date", type=str, default=None,
                       help="End date for paper retrieval")
    
    parser.add_argument("--generate-email", type=bool, default=True,
                       help="Whether to generate an email")
    
    parser.add_argument("--publish-podcast", type=bool, default=False,
                       help="Whether to publish the podcast")
    
    parser.add_argument("--intro-music-path", type=str, default=None,
                       help="Path to the intro music file")
    
    parser.add_argument("--generate-podcast", type=bool, default=False,
                       help="Whether to generate a podcast")
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    theseus_insight = TheseusInsight(
        research_interests_path=args.research_interests_path,
        n_days=args.n_days,
        top_n=args.top_n,
        orchestration_config=args.orchestration_config,
        receiver_address=args.receiver_address,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        cosine_similarity_threshold=args.cosine_similarity_threshold,
        db_saving=args.db_saving,
        data_path=args.db_url,
        verbose=args.verbose,
        start_date=args.start_date,
        end_date=args.end_date,
        generate_email=args.generate_email,
        publish_podcast=args.publish_podcast,
        intro_music_path=args.intro_music_path,
        generate_podcast=args.generate_podcast
    )
    
    theseus_insight.run()