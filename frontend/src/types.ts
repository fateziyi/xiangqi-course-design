export type Side = 'red'|'black';
export type Mode = 'human_human'|'human_ai'|'ai_ai';
export interface Move {from:number;to:number}
export interface AIConfig {maxDepth:number;timeLimitMs:number;engine?:'self'|'pikafish'}
export interface Result {winner:Side|null;reason:'checkmate'|'stalemate'|'threefold'|'no_capture_limit'}
export interface GameState {
  gameId:string;revision:number;mode:Mode;humanSide:Side|null;redAI:AIConfig;blackAI:AIConfig;
  board:number[];sideToMove:Side;status:'active'|'finished';control:'running'|'paused'|'replay';
  inCheck:boolean;result:Result|null;lastMove:Move|null;historyLength:number;displayPly:number;
  displayStatus:'active'|'finished';displayResult:Result|null;legalMoves:Move[];
  thinking:null|{purpose:'move'|'recommend';side:Side};
}
export interface State {protocolVersion:1;type:'state';game:GameState|null;stats:{redWins:number;blackWins:number;draws:number}}
