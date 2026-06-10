import React from 'react';
import { Autocomplete, Box, TextField, Typography } from '@mui/material';

// Interface for model catalog entries
export interface ModelCatalogOption {
  id: number;
  alias: string;
  model_string: string;
  provider_name: string;
  model_type: string;
  display: string; // "Alias (model_string)"
}

// Component for model name autocomplete with catalog integration
interface ModelNameAutocompleteProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onModelSelected?: (model: any) => void; // Called when a catalog model is selected
  modelCatalogData?: any;
  fullWidth?: boolean;
}

export const ModelNameAutocomplete: React.FC<ModelNameAutocompleteProps> = ({
  label,
  value,
  onChange,
  onModelSelected,
  modelCatalogData,
  fullWidth = true
}) => {
  // Transform model catalog data into options
  const catalogOptions: ModelCatalogOption[] = React.useMemo(() => {
    if (!modelCatalogData?.models) {
      return [];
    }
    
    const options = modelCatalogData.models.map((model: any) => ({
      id: model.id,
      alias: model.alias,
      model_string: model.model_string,
      provider_name: model.provider_name,
      model_type: model.model_type,
      display: `${model.alias} (${model.model_string})`
    }));
    
    return options;
  }, [modelCatalogData]);

  // Find the currently selected option based on model_string
  const selectedOption = catalogOptions.find(opt => opt.model_string === value) || null;

  const handleChange = (_: any, newValue: ModelCatalogOption | string | null) => {
    if (typeof newValue === 'string') {
      // User typed a custom value
      onChange(newValue);
    } else if (newValue) {
      // User selected from catalog - update the input field immediately and call batch update
      onChange(newValue.model_string);
      if (onModelSelected) {
        onModelSelected(newValue);
      }
    } else {
      // Cleared
      onChange('');
    }
  };

  return (
    <Autocomplete
      fullWidth={fullWidth}
      freeSolo
      options={catalogOptions}
      getOptionLabel={(option) => {
        if (typeof option === 'string') return option;
        return option.display;
      }}
      renderOption={(props, option) => (
        <li {...props} key={option.id}>
          <Box>
            <Typography variant="body2" fontWeight={500}>
              {option.alias}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {option.model_string} • {option.provider_name}
            </Typography>
          </Box>
        </li>
      )}
      value={selectedOption}
      onChange={handleChange}
      inputValue={selectedOption ? selectedOption.display : value}
      blurOnSelect={true}
      selectOnFocus={true}
      clearOnBlur={false}
      onInputChange={(_, newInputValue, reason) => {
        if (reason === 'clear') {
          onChange('');
        } else if (reason === 'input' && !selectedOption) {
          onChange(newInputValue);
        }
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          helperText={catalogOptions.length > 0 ? 
            `Search model catalog (${catalogOptions.length} models) or enter custom model name` : 
            "Model catalog not loaded - enter custom model name"
          }
        />
      )}
      filterOptions={(options, { inputValue }) => {
        if (!inputValue) return options.slice(0, 10); // Show first 10 when no input
        
        const filtered = options.filter(option =>
          option.alias.toLowerCase().includes(inputValue.toLowerCase()) ||
          option.model_string.toLowerCase().includes(inputValue.toLowerCase()) ||
          option.provider_name.toLowerCase().includes(inputValue.toLowerCase())
        );
        
        return filtered.slice(0, 20); // Limit to 20 results
      }}
    />
  );
};
