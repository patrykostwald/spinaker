const base = require('./109-fixture.cjs');
const messages = Object.fromEntries(['government','opposition'].map((camp,i) => [camp, {
 ...base.page.messages[camp], id: 111+i, comment_count: 0, opinions:{positive:0,negative:0},
 thesis: 'Teza testowa o wspólnych sprawach',
 points: [{title:'Argument',summary:'Przykład syntetyczny do sprawdzenia układu i dyskusji.',authors:['Osoba testowa'],post_ids:['1']},{title:'Kontekst',summary:'Obie strony mają identyczne możliwości komentowania.',authors:['Druga osoba'],post_ids:['2']}],
 analysis: 'Analiza testowa. Źródła i komentarze są rozdzielone, a ocena analizy jest niezależna od dyskusji.', posts:[], posts_count:0,
 stats:{version:1,posts:12,authors:4,noise:0,concrete_count:6,concrete_pct:50,coherence_authors:3,coherence_pct:75,tone:{atak:25,osiagniecie:25,apel:25,inne:25},tone_classified:12}
}]));
const day = {day:'2026-10-09',...messages};
const interview = {...base.interview,comment_count:0,opinions:{positive:0,negative:0}};
const page = {...base.page,messages,interview};
function response(path) {
 if(/\/api\/clinic\/daily-messages\/\d+\/opinions\/$/.test(path)) return {counts:{positive:0,negative:0},mine:null};
 if(/\/api\/clinic\/daily-messages\/\d+\/comments\/$/.test(path)) return {results:[{id:1,author:{id:7,username:'czytelnik'},body:'Przykładowy komentarz pod przekazem dnia.',hidden:false,hidden_reason:'',parent:null,created_at:'2026-10-09T08:00:00Z',reply_count:0}],next_page:null,count:1};
 if(path==='/api/clinic/') return page;
 if(path==='/api/clinic/messages/2026-10-09/') return day;
 if(path==='/api/clinic/messages/') return {results:[day],count:1,next_page:null};
 if(path==='/api/clinic/interviews/') return {results:[interview],count:1,next_page:null,channels:[]};
 if(path==='/api/clinic/interviews/109/') return interview;
 return base.response(path);
}
module.exports={...base,page,day,interview,response};
