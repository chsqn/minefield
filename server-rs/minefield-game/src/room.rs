use failure::{Error, Fail};
use serde::{Deserialize, Serialize};

use crate::game::Game;
use crate::protocol::{Msg, PGame};

#[derive(Debug, Fail)]
pub enum RoomError {
    #[fail(display = "already joined")]
    AlreadyJoined,
    #[fail(display = "game not started")]
    GameNotStarted,
    #[fail(display = "game finished")]
    GameFinished,
}

#[derive(Serialize, Deserialize)]
pub struct Room {
    game: Option<Game>,
    #[serde(skip)]
    user_ids: [Option<usize>; 2],
    nicks: [String; 2],
    pub room_key: String,
    pub player_keys: [String; 2],
    messages: [Vec<Msg>; 2],
}

impl Room {
    pub fn new(user_id: usize, nick: String) -> Self {
        Room {
            game: None,
            user_ids: [Some(user_id), None],
            nicks: [nick, "".to_owned()],
            room_key: Self::gen_key(),
            player_keys: [Self::gen_key(), Self::gen_key()],
            messages: [vec![], vec![]],
        }
    }

    fn gen_key() -> String {
        use rand::seq::IteratorRandom;

        let chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
        chars
            .chars()
            .choose_multiple(&mut rand::thread_rng(), 10)
            .iter()
            .collect()
    }

    pub fn describe(&self) -> Option<PGame> {
        match self.game.as_ref() {
            Some(game) if game.finished => None,
            Some(_) => Some(PGame::Game {
                nicks: self.nicks.clone(),
            }),
            None if self.user_ids[0].is_some() => Some(PGame::Player {
                nick: self.nicks[0].clone(),
                key: self.room_key.clone(),
            }),
            None => None,
        }
    }

    pub fn beat(&mut self) -> Vec<(usize, Msg)> {
        match self.game.as_mut() {
            Some(game) if !game.finished => {
                game.beat();
                self.messages()
            }
            _ => vec![],
        }
    }

    pub fn started(&self) -> bool {
        self.game.is_some()
    }

    pub fn finished(&self) -> bool {
        let game_finished = match self.game.as_ref() {
            Some(game) => game.finished,
            None => true,
        };
        game_finished && self.user_ids[0].is_none() && self.user_ids[1].is_none()
    }

    pub fn connect(&mut self, user_id: usize, nick: String) -> Result<Vec<(usize, Msg)>, Error> {
        if self.user_ids[1].is_some() || self.game.is_some() {
            return Err(RoomError::AlreadyJoined.into());
        }

        self.user_ids[1] = Some(user_id);
        self.nicks[1] = nick;

        assert!(self.user_ids[0] != self.user_ids[1]);

        let mut messages = vec![];
        for i in 0..2 {
            if let Some(user_id) = self.user_ids[i] {
                let msg = Msg::Room {
                    you: i,
                    nicks: self.nicks.clone(),
                    key: self.player_keys[i].clone(),
                };
                self.messages[i].push(msg.clone());
                messages.push((user_id, msg));
            }
        }

        let mut game = Game::new(&mut rand::thread_rng());
        game.on_start();
        self.game = Some(game);

        messages.append(&mut self.messages());
        Ok(messages)
    }

    pub fn rejoin(&mut self, user_id: usize, i: usize) -> Result<Vec<(usize, Msg)>, Error> {
        if self.user_ids[i].is_some() {
            return Err(RoomError::AlreadyJoined.into());
        }

        self.user_ids[i] = Some(user_id);
        assert!(self.user_ids[0] != self.user_ids[1]);

        let mut replayed: Vec<(usize, Msg)> = self.messages[i]
            .iter()
            .map(|msg| {
                (
                    user_id,
                    Msg::Replay {
                        msg: Box::new(msg.clone()),
                    },
                )
            })
            .collect();

        if let Some(ref game) = self.game {
            if !game.finished {
                if let Some(msg) = game.rejoin_msg(i) {
                    replayed.push((user_id, Msg::Replay { msg: Box::new(msg) }))
                }
            }
        }

        Ok(replayed)
    }

    pub fn disconnect(&mut self, user_id: usize) {
        let i = self.find_player(user_id).unwrap();
        self.user_ids[i] = None;
    }

    pub fn on_message(&mut self, user_id: usize, msg: Msg) -> Result<Vec<(usize, Msg)>, Error> {
        let i = self.find_player(user_id).unwrap();

        let game = self.game.as_mut().ok_or(RoomError::GameNotStarted)?;
        if game.finished {
            return Err(RoomError::GameFinished.into());
        }

        game.on_message(i, msg);
        Ok(self.messages())
    }

    fn find_player(&self, user_id: usize) -> Option<usize> {
        if self.user_ids[0] == Some(user_id) {
            Some(0)
        } else if self.user_ids[1] == Some(user_id) {
            Some(1)
        } else {
            None
        }
    }

    fn messages(&mut self) -> Vec<(usize, Msg)> {
        let mut result = vec![];
        let game = self.game.as_mut().unwrap();
        for (i, msg) in game.messages().into_iter() {
            // Add messsage for replaying
            self.messages[i].push(msg.clone());

            // Return if there's user connected
            if let Some(user_id) = self.user_ids[i] {
                result.push((user_id, msg));
            }
        }
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use minefield_core::tiles::Tile;

    #[test]
    fn test_new_game() {
        let room = Room::new(33, "Akagi".to_owned());
        assert_eq!(room.finished(), false);
        assert_eq!(
            room.describe(),
            Some(PGame::Player {
                nick: "Akagi".to_owned(),
                key: room.room_key.clone(),
            })
        );
    }

    #[test]
    fn test_join() {
        let mut room = Room::new(33, "Akagi".to_owned());
        let messages = room.connect(55, "Washizu".to_owned()).unwrap();

        assert_eq!(
            room.describe(),
            Some(PGame::Game {
                nicks: ["Akagi".to_owned(), "Washizu".to_owned()],
            })
        );

        assert_eq!(messages.len(), 6);
        // println!("{:?}", messages);
        assert!(matches!(messages[0], (33, Msg::Room { .. })));
        assert!(matches!(messages[1], (55, Msg::Room { .. })));
        assert!(matches!(messages[2], (33, Msg::PhaseOne { .. })));
        assert!(matches!(messages[3], (33, Msg::StartMove { .. })));
        assert!(matches!(messages[4], (55, Msg::PhaseOne { .. })));
        assert!(matches!(messages[5], (55, Msg::StartMove { .. })));
    }

    fn replayed(msg: &Msg) -> Option<&Msg> {
        match msg {
            Msg::Replay { msg } => Some(msg),
            _ => None,
        }
    }

    #[test]
    fn test_rejoin() {
        let mut room = Room::new(33, "Akagi".to_owned());
        room.connect(55, "Washizu".to_owned()).unwrap();
        room.disconnect(55);

        assert_eq!(room.user_ids[1], None);
        let messages = room.rejoin(55, 1).unwrap();
        assert_eq!(room.user_ids[1], Some(55));
        assert_eq!(messages.len(), 4);
        assert!(matches!(messages[0], (55, Msg::Replay { .. })));
        assert!(matches!(replayed(&messages[0].1).unwrap(), Msg::Room {..}));
        assert!(matches!(messages[1], (55, Msg::Replay { .. })));
        assert!(matches!(replayed(&messages[1].1).unwrap(), Msg::PhaseOne {..}));
        assert!(matches!(messages[2], (55, Msg::Replay { .. })));
        assert!(matches!(replayed(&messages[2].1).unwrap(), Msg::StartMove {..}));

        // another StartMove with right time
        assert!(matches!(messages[3], (55, Msg::Replay { .. })));
        assert!(matches!(replayed(&messages[3].1).unwrap(), Msg::StartMove {..}));
    }

    #[test]
    fn test_on_message() {
        let mut room = Room::new(33, "Akagi".to_owned());
        let messages = room.connect(55, "Washizu".to_owned()).unwrap();

        let hand = match messages[2].1 {
            Msg::PhaseOne { ref tiles, .. } => tiles[0..13].to_vec(),
            _ => unreachable!("wrong message"),
        };

        let messages = room
            .on_message(33, Msg::Hand { hand: hand.clone() })
            .unwrap();

        assert_eq!(
            messages,
            vec![
                (33, Msg::EndMove),
                (33, Msg::Hand { hand: hand.clone() }),
                (33, Msg::WaitForPhaseTwo),
            ]
        );
    }

    #[test]
    fn test_on_message_abort() {
        let mut room = Room::new(33, "Akagi".to_owned());
        room.connect(55, "Washizu".to_owned()).unwrap();
        let messages = room
            .on_message(33, Msg::Discard { tile: Tile::M1 })
            .unwrap();
        println!("{:?}", messages);
        assert_eq!(
            messages,
            vec![
                (
                    33,
                    Msg::Abort {
                        culprit: 0,
                        description: "discard too soon".to_owned(),
                    }
                ),
                (
                    55,
                    Msg::Abort {
                        culprit: 0,
                        description: "discard too soon".to_owned(),
                    }
                )
            ]
        );
        assert_eq!(room.finished(), false);
        assert_eq!(room.describe(), None);

        room.disconnect(33);
        room.disconnect(55);
        assert_eq!(room.finished(), true);
        assert_eq!(room.describe(), None);
    }
}
