type ParseTweet = (text: string) => { weightedLength: number; valid: boolean };
// Import only the parser. The package root resolves to an ESM namespace in
// Next's browser build, while Node resolves its CommonJS object differently.
const parserModule = require('twitter-text/dist/parseTweet') as ParseTweet | { default: ParseTweet };
const parseTweet: ParseTweet = typeof parserModule === 'function' ? parserModule : parserModule.default;
export const measurePost = (text: string) => parseTweet(text);
