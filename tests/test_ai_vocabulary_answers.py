import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ai.schemas import VocabularyAnswerCheckResult
from ai.vocabulary_answers import check_vocabulary_answer
from enums import (
    AIRequestInitiator,
    AIRequestScenario,
    TextModel,
    VocabularyAnswerVerdict,
)


class AIVocabularyAnswerTest(unittest.IsolatedAsyncioTestCase):
    async def test_uses_gpt_4o_mini_structured_output(self):
        parsed_result = VocabularyAnswerCheckResult(
            verdict=VocabularyAnswerVerdict.CORRECT,
            comment=None,
        )
        usage = Mock(
            input_tokens=20,
            output_tokens=5,
            total_tokens=25,
        )
        usage.input_tokens_details.cached_tokens = 0
        usage.output_tokens_details.reasoning_tokens = 0
        response = Mock(output_parsed=parsed_result, usage=usage)
        client = Mock()
        client.responses.parse = AsyncMock(return_value=response)
        save_usage = AsyncMock()

        with (
            patch('ai.vocabulary_answers.get_openai_client', return_value=client),
            patch('ai.vocabulary_answers.save_text_model_usage.kiq', save_usage),
        ):
            result = await check_vocabulary_answer(
                source_text='assignment',
                answer='задание',
                source_language='en',
                target_language='ru',
                part_of_speech='noun',
            )

        self.assertEqual(result, parsed_result)
        request = client.responses.parse.await_args.kwargs
        self.assertEqual(request['model'], TextModel.GPT_4O_MINI.value)
        self.assertIs(request['text_format'], VocabularyAnswerCheckResult)
        input_data = json.loads(request['input'][1]['content'])
        self.assertEqual(
            input_data,
            {
                'source_text': 'assignment',
                'source_language': 'en',
                'target_language': 'ru',
                'part_of_speech': 'noun',
                'learner_answer': 'задание',
            },
        )
        save_usage.assert_awaited_once_with(
            model=TextModel.GPT_4O_MINI.value,
            initiator=AIRequestInitiator.USER.value,
            scenario=AIRequestScenario.WORD_ANSWER_CHECK.value,
            input_tokens=20,
            cached_input_tokens=0,
            output_tokens=5,
            reasoning_tokens=0,
            total_tokens=25,
        )


if __name__ == '__main__':
    unittest.main()
