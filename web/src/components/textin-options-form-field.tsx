import { RAGFlowFormItem } from '@/components/ragflow-form';
import { Input } from '@/components/ui/input';
import { LLMFactory } from '@/constants/llm';
import { useFormContext, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

export function TextInOptionsFormField({
  namePrefix = 'parser_config',
}: {
  namePrefix?: string;
}) {
  const form = useFormContext();
  const { t } = useTranslation();
  const buildName = (field: string) =>
    namePrefix ? `${namePrefix}.${field}` : field;

  const layoutRecognize = useWatch({
    control: form.control,
    name: 'parser_config.layout_recognize',
  });

  // Check if TextIn is selected (the value contains 'TextIn' or matches the factory name)
  const isTextInSelected =
    layoutRecognize?.includes(LLMFactory.TextIn) ||
    layoutRecognize?.toLowerCase()?.includes('textin');

  if (!isTextInSelected) {
    return null;
  }

  return (
    <div className="space-y-4 border-l-2 border-primary/30 pl-4 ml-2">
      <div className="text-sm font-medium text-text-secondary">
        {t('knowledgeConfiguration.textinOptions', 'TextIn Options')}
      </div>

      <RAGFlowFormItem
        name={buildName('textin_api_url')}
        label={t('knowledgeConfiguration.textinApiUrl', 'TextIn API URL')}
        tooltip={t(
          'knowledgeConfiguration.textinApiUrlTip',
          'The API endpoint URL for TextIn service. Default: https://api.textin.com/ai/service/v1/pdf_to_markdown',
        )}
        horizontal={true}
      >
        {(field) => (
          <Input
            {...field}
            placeholder={t(
              'knowledgeConfiguration.textinApiUrlPlaceholder',
              'https://api.textin.com/ai/service/v1/pdf_to_markdown',
            )}
          />
        )}
      </RAGFlowFormItem>

      <RAGFlowFormItem
        name={buildName('textin_app_id')}
        label={t('knowledgeConfiguration.textinAppId', 'TextIn App ID')}
        tooltip={t(
          'knowledgeConfiguration.textinAppIdTip',
          'Your TextIn application ID',
        )}
        horizontal={true}
      >
        {(field) => (
          <Input
            {...field}
            placeholder={t(
              'knowledgeConfiguration.textinAppIdPlaceholder',
              'Enter your TextIn App ID',
            )}
          />
        )}
      </RAGFlowFormItem>

      <RAGFlowFormItem
        name={buildName('textin_secret_code')}
        label={t('knowledgeConfiguration.textinSecretCode', 'TextIn Secret Code')}
        tooltip={t(
          'knowledgeConfiguration.textinSecretCodeTip',
          'Your TextIn secret code for authentication',
        )}
        horizontal={true}
      >
        {(field) => (
          <Input
            {...field}
            type="password"
            placeholder={t(
              'knowledgeConfiguration.textinSecretCodePlaceholder',
              'Enter your TextIn Secret Code',
            )}
          />
        )}
      </RAGFlowFormItem>
    </div>
  );
}