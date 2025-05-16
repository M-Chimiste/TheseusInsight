"use client";

import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const PROVIDERS = [
  { id: 1, name: "Ollama" },
  { id: 2, name: "Gemini" },
  { id: 3, name: "OpenAI" },
  { id: 4, name: "Sentence Transformers" },
];

const defaultModelConfig = {
  temperature: 0.1,
  num_ctx: 4096,
};

const defaultSTConfig = {
  model_name: "Alibaba-NLP/gte-modernbert-base",
  model_type: "sentence-transformers",
  trust_remote_code: true,
};

export function ModelsTab() {
  const [models, setModels] = useState<any[]>([]);
  const [newModel, setNewModel] = useState<any>({
    provider_id: 0,
    name: '',
    config_json: { ...defaultModelConfig },
  });

  const isSentenceTransformer = newModel.provider_id === 4;

  const handleAddModel = async () => {
    let payload = { ...newModel };
    if (isSentenceTransformer) {
      payload.config_json = {
        model_name: newModel.config_json.model_name,
        model_type: "sentence-transformers",
        trust_remote_code: newModel.config_json.trust_remote_code,
      };
    }
    try {
      const response = await fetch('/api/models', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error('Failed to add model');
      }
      const addedModel = await response.json();
      setModels([...models, addedModel]);
      setNewModel({
        provider_id: 0,
        name: '',
        config_json: isSentenceTransformer ? { ...defaultSTConfig } : { ...defaultModelConfig },
      });
      toast.success("Model added successfully");
    } catch (error) {
      toast.error("Failed to add model");
    }
  };

  const handleDeleteModel = async (id: number) => {
    try {
      const response = await fetch(`/api/models/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error('Failed to delete model');
      }
      setModels(models.filter(model => model.id !== id));
      toast.success("Model deleted successfully");
    } catch (error) {
      toast.error("Failed to delete model");
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Add New Model</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider</Label>
                <Select
                  value={newModel.provider_id?.toString()}
                  onValueChange={(value: string) => {
                    const pid = parseInt(value);
                    setNewModel({
                      ...newModel,
                      provider_id: pid,
                      config_json: pid === 4 ? { ...defaultSTConfig } : { ...defaultModelConfig },
                    });
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {PROVIDERS.map((p) => (
                      <SelectItem key={p.id} value={p.id.toString()}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Model Name</Label>
                <Input
                  id="name"
                  value={isSentenceTransformer ? newModel.config_json.model_name : newModel.name}
                  onChange={(e) => {
                    if (isSentenceTransformer) {
                      setNewModel({
                        ...newModel,
                        config_json: {
                          ...newModel.config_json,
                          model_name: e.target.value,
                        },
                      });
                    } else {
                      setNewModel({ ...newModel, name: e.target.value });
                    }
                  }}
                  placeholder={isSentenceTransformer ? "e.g., Alibaba-NLP/gte-modernbert-base" : "e.g., gemma3:27b-it-qat"}
                />
              </div>
            </div>
            {isSentenceTransformer ? (
              <div className="space-y-2">
                <Label htmlFor="trust_remote_code">Trust Remote Code</Label>
                <input
                  id="trust_remote_code"
                  type="checkbox"
                  checked={newModel.config_json.trust_remote_code}
                  onChange={(e) => setNewModel({
                    ...newModel,
                    config_json: {
                      ...newModel.config_json,
                      trust_remote_code: e.target.checked,
                    },
                  })}
                  className="ml-2"
                />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="temperature">Temperature</Label>
                  <Input
                    id="temperature"
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={newModel.config_json?.temperature ?? defaultModelConfig.temperature}
                    onChange={(e) => setNewModel({
                      ...newModel,
                      config_json: {
                        ...newModel.config_json,
                        temperature: parseFloat(e.target.value),
                        num_ctx: newModel.config_json?.num_ctx ?? defaultModelConfig.num_ctx,
                      },
                    })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="num_ctx">Context Length</Label>
                  <Input
                    id="num_ctx"
                    type="number"
                    value={newModel.config_json?.num_ctx ?? defaultModelConfig.num_ctx}
                    onChange={(e) => setNewModel({
                      ...newModel,
                      config_json: {
                        ...newModel.config_json,
                        temperature: newModel.config_json?.temperature ?? defaultModelConfig.temperature,
                        num_ctx: parseInt(e.target.value),
                      },
                    })}
                  />
                </div>
              </div>
            )}
          </div>
        </CardContent>
        <CardFooter>
          <Button onClick={handleAddModel}>Add Model</Button>
        </CardFooter>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {models.map((model) => {
          const isST = model.provider_id === 4;
          return (
            <Card key={model.id}>
              <CardHeader>
                <CardTitle className="text-lg">{isST ? model.config_json.model_name : model.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    Provider: {PROVIDERS.find(p => p.id === model.provider_id)?.name}
                  </p>
                  {isST ? (
                    <>
                      <p className="text-sm text-muted-foreground">
                        Trust Remote Code: {model.config_json.trust_remote_code ? 'Yes' : 'No'}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-sm text-muted-foreground">
                        Temperature: {model.config_json.temperature}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Context Length: {model.config_json.num_ctx}
                      </p>
                    </>
                  )}
                </div>
              </CardContent>
              <CardFooter>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => model.id && handleDeleteModel(model.id)}
                >
                  Delete
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>
    </div>
  );
} 