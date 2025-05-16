"use client";

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface Model {
  id: number;
  name: string;
  provider_id: number;
  config_json: {
    temperature: number;
    num_ctx: number;
    max_new_tokens?: number;
  };
}

interface ModelConfig {
  model_id: number;
  temperature: number;
  num_ctx: number;
}

interface EmbeddingModelConfig {
  model_id: number;
}

interface OrchestrationConfig {
  judge_model: ModelConfig;
  newsletter_model: ModelConfig;
  content_extraction_model: ModelConfig;
  newsletter_sections_model: ModelConfig;
  newsletter_intro_model: ModelConfig;
  embedding_model: EmbeddingModelConfig;
  podcast_model: ModelConfig;
  tts_model: {
    tts_provider: string;
    tts_model_name: string;
    speaker_1_voice: string;
    speaker_1_speed: number;
    speaker_2_voice: string;
    speaker_2_speed: number;
  };
  arxiv_search_categories: {
    main_category: string;
    filter_categories: string[];
  };
}

export function OrchestrationTab() {
  const [models, setModels] = useState<Model[]>([]);
  const [config, setConfig] = useState<OrchestrationConfig>({
    judge_model: {
      model_id: 0,
      temperature: 0.1,
      num_ctx: 4096,
    },
    newsletter_model: {
      model_id: 0,
      temperature: 0.1,
      num_ctx: 4096,
    },
    content_extraction_model: {
      model_id: 0,
      temperature: 0.1,
      num_ctx: 4096,
    },
    newsletter_sections_model: {
      model_id: 0,
      temperature: 0.1,
      num_ctx: 4096,
    },
    newsletter_intro_model: {
      model_id: 0,
      temperature: 0.1,
      num_ctx: 4096,
    },
    embedding_model: {
      model_id: 0,
    },
    podcast_model: {
      model_id: 0,
      temperature: 0.1,
      num_ctx: 4096,
    },
    tts_model: {
      tts_provider: 'openai',
      tts_model_name: 'tts-1',
      speaker_1_voice: 'sage',
      speaker_1_speed: 1.0,
      speaker_2_voice: 'ash',
      speaker_2_speed: 1.0,
    },
    arxiv_search_categories: {
      main_category: 'cs',
      filter_categories: ['cs.ai', 'cs.cl', 'cs.lg', 'cs.ir', 'cs.ma', 'cs.cv'],
    },
  });

  useEffect(() => {
    // Fetch available models
    const fetchModels = async () => {
      try {
        const response = await fetch('/api/models');
        if (!response.ok) throw new Error('Failed to fetch models');
        const data = await response.json();
        setModels(data);
      } catch (error) {
        toast.error('Failed to load models');
      }
    };

    // Fetch current orchestration config
    const fetchConfig = async () => {
      try {
        const response = await fetch('/api/settings/orchestration');
        if (!response.ok) throw new Error('Failed to fetch orchestration config');
        const data = await response.json();
        setConfig(data);
      } catch (error) {
        toast.error('Failed to load orchestration config');
      }
    };

    fetchModels();
    fetchConfig();
  }, []);

  const handleSave = async () => {
    try {
      const response = await fetch('/api/settings/orchestration', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error('Failed to save orchestration config');
      toast.success('Orchestration configuration saved successfully');
    } catch (error) {
      toast.error('Failed to save orchestration configuration');
    }
  };

  const renderModelConfig = (
    title: string,
    key: keyof OrchestrationConfig,
    showParams: boolean = true
  ) => {
    const modelConfig = config[key];
    if (!('model_id' in modelConfig)) return null;

    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Model</Label>
              <Select
                value={modelConfig.model_id.toString()}
                onValueChange={(value: string) => {
                  setConfig({
                    ...config,
                    [key]: {
                      ...modelConfig,
                      model_id: parseInt(value),
                    },
                  });
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((model) => (
                    <SelectItem key={model.id} value={model.id.toString()}>
                      {model.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {showParams && 'temperature' in modelConfig && 'num_ctx' in modelConfig && (
              <>
                <div className="space-y-2">
                  <Label>Temperature</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={modelConfig.temperature}
                    onChange={(e) => {
                      setConfig({
                        ...config,
                        [key]: {
                          ...modelConfig,
                          temperature: parseFloat(e.target.value),
                        },
                      });
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Context Length</Label>
                  <Input
                    type="number"
                    value={modelConfig.num_ctx}
                    onChange={(e) => {
                      setConfig({
                        ...config,
                        [key]: {
                          ...modelConfig,
                          num_ctx: parseInt(e.target.value),
                        },
                      });
                    }}
                  />
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {renderModelConfig('Judge Model', 'judge_model')}
        {renderModelConfig('Newsletter Model', 'newsletter_model')}
        {renderModelConfig('Content Extraction Model', 'content_extraction_model')}
        {renderModelConfig('Newsletter Sections Model', 'newsletter_sections_model')}
        {renderModelConfig('Newsletter Intro Model', 'newsletter_intro_model')}
        {renderModelConfig('Embedding Model', 'embedding_model', false)}
        {renderModelConfig('Podcast Model', 'podcast_model')}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>TTS Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>TTS Provider</Label>
              <Input
                value={config.tts_model.tts_provider}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    tts_model: {
                      ...config.tts_model,
                      tts_provider: e.target.value,
                    },
                  });
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Model Name</Label>
              <Input
                value={config.tts_model.tts_model_name}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    tts_model: {
                      ...config.tts_model,
                      tts_model_name: e.target.value,
                    },
                  });
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Speaker 1 Voice</Label>
              <Input
                value={config.tts_model.speaker_1_voice}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    tts_model: {
                      ...config.tts_model,
                      speaker_1_voice: e.target.value,
                    },
                  });
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Speaker 1 Speed</Label>
              <Input
                type="number"
                step="0.1"
                value={config.tts_model.speaker_1_speed}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    tts_model: {
                      ...config.tts_model,
                      speaker_1_speed: parseFloat(e.target.value),
                    },
                  });
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Speaker 2 Voice</Label>
              <Input
                value={config.tts_model.speaker_2_voice}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    tts_model: {
                      ...config.tts_model,
                      speaker_2_voice: e.target.value,
                    },
                  });
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Speaker 2 Speed</Label>
              <Input
                type="number"
                step="0.1"
                value={config.tts_model.speaker_2_speed}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    tts_model: {
                      ...config.tts_model,
                      speaker_2_speed: parseFloat(e.target.value),
                    },
                  });
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>ArXiv Search Categories</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Main Category</Label>
              <Input
                value={config.arxiv_search_categories.main_category}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    arxiv_search_categories: {
                      ...config.arxiv_search_categories,
                      main_category: e.target.value,
                    },
                  });
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Filter Categories (comma-separated)</Label>
              <Input
                value={config.arxiv_search_categories.filter_categories.join(', ')}
                onChange={(e) => {
                  setConfig({
                    ...config,
                    arxiv_search_categories: {
                      ...config.arxiv_search_categories,
                      filter_categories: e.target.value.split(',').map(cat => cat.trim()),
                    },
                  });
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Button onClick={handleSave}>Save Configuration</Button>
    </div>
  );
} 